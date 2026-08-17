"""Notification engine: email + in-app alerts for every service desk event."""

import frappe
from frappe.utils import get_link_to_form, get_url_to_form, now_datetime

from turacoz_service_desk.turacoz_it_service_desk.engine import utils

# event -> (subject template, body template)
TEMPLATES = {
	"new_ticket": (
		"[{name}] New ticket: {title}",
		"A new ticket has been raised.<br><b>Priority:</b> {priority}<br>"
		"<b>Category:</b> {category}<br><b>Requester:</b> {requester}",
	),
	"assignment": (
		"[{name}] Assigned to you: {title}",
		"This ticket has been assigned to you.<br><b>Priority:</b> {priority}<br>"
		"<b>Respond by:</b> {response_by}<br><b>Resolve by:</b> {resolution_by}",
	),
	"status_change": (
		"[{name}] Status changed to {status}",
		"The status of <b>{title}</b> is now <b>{status}</b>.",
	),
	"comment": (
		"[{name}] New comment on {title}",
		"A new comment was added.<br><br>{extra_message}",
	),
	"approval_pending": (
		"[{name}] Approval required: {title}",
		"Your approval is required for <b>{title}</b>.",
	),
	"approval_approved": (
		"[{name}] Approved: {title}",
		"<b>{title}</b> has been approved.",
	),
	"approval_rejected": (
		"[{name}] Rejected: {title}",
		"<b>{title}</b> has been rejected.",
	),
	"resolution": (
		"[{name}] Resolved: {title}",
		"Your ticket has been resolved. Please verify and confirm closure.",
	),
	"closure": (
		"[{name}] Closed: {title}",
		"Your ticket has been closed. Thank you.",
	),
	"reopened": (
		"[{name}] Reopened: {title}",
		"This ticket has been reopened by the requester.",
	),
	"sla_breach": (
		"[{name}] SLA breached: {title}",
		"The {extra_breach} SLA for this ticket has been breached.<br>"
		"<b>Priority:</b> {priority}<br><b>Engineer:</b> {assigned_engineer}",
	),
	"sla_reminder": (
		"[{name}] SLA at {extra_percent}%: {title}",
		"This ticket has consumed {extra_percent}% of its resolution SLA.",
	),
	"escalation": (
		"[{name}] Escalated: {title}",
		"This ticket has been escalated (level {escalation_level}).<br>"
		"<b>Priority:</b> {priority}",
	),
	"feedback_request": (
		"[{name}] How did we do? {title}",
		"Your ticket has been closed. Please rate the support you received.",
	),
	"access_granted": (
		"[{name}] Privileged access granted",
		"Privileged access has been granted and expires on {valid_till}.",
	),
	"access_expiring": (
		"[{name}] Privileged access expiring",
		"Privileged access expires on {valid_till} and will be revoked automatically.",
	),
	"access_revoked": (
		"[{name}] Privileged access revoked",
		"Privileged access has been revoked.",
	),
}

STATUS_ONLY_EVENTS = ("status_change", "resolution", "closure", "reopened")
RESOLUTION_ONLY_EVENTS = ("resolution", "closure")


# ---------------------------------------------------------------------------
# recipients
# ---------------------------------------------------------------------------

def default_recipients(doc, event):
	requester = doc.get("requester") or doc.get("requested_by") or doc.owner
	engineer = doc.get("assigned_engineer")
	lead = None
	if doc.get("assigned_team"):
		lead = frappe.db.get_value("Service Desk Team", doc.assigned_team, "team_lead")

	mapping = {
		"new_ticket": [engineer, lead],
		"assignment": [engineer],
		"status_change": [requester],
		"comment": [requester, engineer],
		"approval_pending": _pending_approvers(doc),
		"approval_approved": [requester, engineer],
		"approval_rejected": [requester, engineer],
		"resolution": [requester],
		"closure": [requester],
		"reopened": [engineer, lead],
		"sla_breach": [engineer, lead],
		"sla_reminder": [engineer, lead],
		"escalation": [lead],
		"feedback_request": [requester],
		"access_granted": [requester, doc.get("requested_for")],
		"access_expiring": [requester, doc.get("requested_for")],
		"access_revoked": [requester, doc.get("requested_for")],
	}
	recipients = [u for u in mapping.get(event, [requester]) if u]
	recipients.extend(_watchers(doc, event))
	return recipients


def _pending_approvers(doc):
	from turacoz_service_desk.turacoz_it_service_desk.engine import approval

	out = []
	for row in approval.pending_rows(doc):
		if row.approver:
			out.append(row.approver)
		elif row.approver_role:
			out.extend(utils.get_users_with_role(row.approver_role))
	return out


def _watchers(doc, event):
	if not doc.meta.has_field("watchers") or not utils.setting("notify_watchers", 1):
		return []
	out = []
	for row in doc.get("watchers", []):
		if row.notify_on == "All Updates":
			out.append(row.user)
		elif row.notify_on == "Status Change" and event in STATUS_ONLY_EVENTS:
			out.append(row.user)
		elif row.notify_on == "Resolution Only" and event in RESOLUTION_ONLY_EVENTS:
			out.append(row.user)
	return out


def _valid_emails(recipients):
	seen, out = set(), []
	for user in recipients:
		if not user or user in seen or user in ("Administrator", "Guest"):
			seen.add(user)
			continue
		seen.add(user)
		row = frappe.db.get_value("User", user, ["email", "enabled"], as_dict=True)
		if row and row.enabled and row.email:
			out.append((user, row.email))
	return out


# ---------------------------------------------------------------------------
# sending
# ---------------------------------------------------------------------------

def _context(doc, extra):
	context = {
		"name": doc.name,
		"title": doc.get("subject") or doc.get("title") or doc.name,
		"status": doc.get("status"),
		"priority": doc.get("priority"),
		"category": doc.get("category"),
		"requester": doc.get("requester") or doc.owner,
		"assigned_engineer": doc.get("assigned_engineer") or "-",
		"response_by": doc.get("response_by") or "-",
		"resolution_by": doc.get("resolution_by") or "-",
		"escalation_level": doc.get("escalation_level") or 0,
		"valid_till": doc.get("valid_till") or "-",
	}
	for key, value in (extra or {}).items():
		context[f"extra_{key}"] = value
	context.setdefault("extra_message", "")
	return context


def notify(doc, event, recipients=None, extra=None, message=None):
	"""Send an event notification. Never raises - notification failure must not block work."""
	try:
		_notify(doc, event, recipients, extra, message)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Service desk notification failed: {event}")


def _notify(doc, event, recipients, extra, message):
	if event not in TEMPLATES:
		return

	send_email = utils.setting("send_email_notifications", 1)
	send_system = utils.setting("send_system_notifications", 1)
	if event in ("sla_breach", "escalation") and not utils.setting("notify_on_sla_breach", 1):
		return
	if not send_email and not send_system:
		return

	targets = _valid_emails(recipients or default_recipients(doc, event))
	targets = [t for t in targets if t[0] != frappe.session.user or event.startswith("approval")]
	if not targets:
		return

	subject_template, body_template = TEMPLATES[event]
	context = _context(doc, extra)
	subject = subject_template.format(**context)
	body = message or body_template.format(**context)
	link = get_link_to_form(doc.doctype, doc.name)
	html = f"{body}<br><br>{link}"

	for user, email in targets:
		if send_email:
			try:
				frappe.sendmail(
					recipients=[email],
					subject=subject,
					message=html,
					reference_doctype=doc.doctype,
					reference_name=doc.name,
					now=False,
				)
				_record(doc, "Email", email, event, subject, "Sent")
			except Exception as exc:
				_record(doc, "Email", email, event, subject, "Failed", str(exc))

		if send_system:
			try:
				frappe.get_doc({
					"doctype": "Notification Log",
					"subject": subject,
					"email_content": html,
					"for_user": user,
					"type": "Alert",
					"document_type": doc.doctype,
					"document_name": doc.name,
					"link": get_url_to_form(doc.doctype, doc.name),
				}).insert(ignore_permissions=True)
				_record(doc, "System", user, event, subject, "Sent")
			except Exception as exc:
				_record(doc, "System", user, event, subject, "Failed", str(exc))


def _record(doc, channel, recipient, event, subject, status, error=None):
	"""Log the notification on the parent document when it tracks them."""
	if not doc.meta.has_field("notifications_sent"):
		return
	row = {
		"channel": channel,
		"recipient": recipient,
		"trigger_event": event,
		"sent_on": now_datetime(),
		"status": status,
		"subject": subject[:140],
		"error": (error or "")[:500],
	}
	if doc.is_new() or doc.flags.in_insert:
		doc.append("notifications_sent", row)
		return
	try:
		child = frappe.get_doc({
			"doctype": "Notification Sent",
			"parent": doc.name,
			"parenttype": doc.doctype,
			"parentfield": "notifications_sent",
			**row,
		})
		child.insert(ignore_permissions=True)
	except Exception:
		pass
