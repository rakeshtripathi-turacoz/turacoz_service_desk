"""Immutable audit trail for the service desk (PRD module 20, ISO 27001 / SOC2)."""

import json

import frappe
from frappe.utils import add_days, cint, now_datetime, today

from turacoz_service_desk.turacoz_it_service_desk.engine import utils

AUDITED_DOCTYPES = (
	"Service Ticket",
	"Incident",
	"Problem",
	"Change Request",
	"Privileged Access Request",
	"Knowledge Article",
	"Configuration Item",
	"Work Log",
	"Ticket Comment",
	"SLA Policy",
	"Approval Matrix",
	"Service Desk Team",
	"Service Desk Settings",
)

# fields that change on every save and say nothing about intent
NOISY_FIELDS = {
	"modified", "modified_by", "creation", "owner", "idx", "docstatus", "_user_tags",
	"_comments", "_assign", "_liked_by", "timeline", "sla_events", "notifications_sent",
}


def enabled():
	return bool(utils.setting("enable_audit_log", 1))


def log(reference_doctype, reference_name, action, details=None, user=None):
	"""Write one audit row. Never raises."""
	if not enabled():
		return
	try:
		entry = frappe.get_doc({
			"doctype": "Service Desk Audit Log",
			"timestamp": now_datetime(),
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"action": action,
			"user": user or frappe.session.user,
			"user_full_name": frappe.db.get_value("User", user or frappe.session.user, "full_name"),
			"ip_address": _ip(),
			"browser": _user_agent(),
			"details": json.dumps(details, default=str, indent=1) if details else None,
		})
		entry.flags.ignore_permissions = True
		entry.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Service desk audit log failed")


def _ip():
	try:
		return frappe.local.request_ip
	except Exception:
		return None


def _user_agent():
	try:
		if getattr(frappe.local, "request", None):
			return (frappe.local.request.headers.get("User-Agent") or "")[:200]
	except Exception:
		pass
	return None


# ---------------------------------------------------------------------------
# document hooks
# ---------------------------------------------------------------------------

def on_insert(doc, method=None):
	if doc.doctype not in AUDITED_DOCTYPES:
		return
	log(doc.doctype, doc.name, "Created", {"title": doc.get("subject") or doc.get("title")})


def on_update(doc, method=None):
	if doc.doctype not in AUDITED_DOCTYPES:
		return

	before = doc.get_doc_before_save()
	if not before:
		return

	changed = {}
	for field in doc.meta.get_valid_columns():
		if field in NOISY_FIELDS:
			continue
		old, new = before.get(field), doc.get(field)
		if old != new:
			changed[field] = {"from": old, "to": new}

	if not changed:
		return

	action = "Modified"
	if "status" in changed:
		action = "Status Changed"
	elif "assigned_engineer" in changed:
		action = "Assigned"
	elif "approval_status" in changed:
		action = {"Approved": "Approved", "Rejected": "Rejected"}.get(
			doc.get("approval_status"), "Modified"
		)
	log(doc.doctype, doc.name, action, changed)


def on_trash(doc, method=None):
	if doc.doctype not in AUDITED_DOCTYPES:
		return
	log(doc.doctype, doc.name, "Deleted", {"title": doc.get("subject") or doc.get("title")})


# ---------------------------------------------------------------------------
# retention
# ---------------------------------------------------------------------------

def purge_expired():
	"""Scheduled daily. 0 retention days keeps everything."""
	days = cint(utils.setting("audit_retention_days", 2555))
	if days <= 0:
		return
	cutoff = add_days(today(), -days)
	frappe.db.delete("Service Desk Audit Log", {"timestamp": ["<", cutoff]})
	frappe.db.commit()


@frappe.whitelist()
def get_trail(reference_doctype, reference_name, limit=50):
	"""Audit rows for one record - powers the History tab."""
	frappe.get_doc(reference_doctype, reference_name).check_permission("read")
	return frappe.get_all(
		"Service Desk Audit Log",
		filters={"reference_doctype": reference_doctype, "reference_name": reference_name},
		fields=["name", "timestamp", "action", "user", "user_full_name", "ip_address", "details"],
		order_by="timestamp desc",
		limit=cint(limit),
	)
