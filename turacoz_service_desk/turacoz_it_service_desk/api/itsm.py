"""REST API for incidents, problems, changes, privileged access and the knowledge base."""

import frappe
from frappe import _
from frappe.utils import cint

from turacoz_service_desk.turacoz_it_service_desk.api.response import api, ok
from turacoz_service_desk.turacoz_it_service_desk.engine import approval, knowledge, utils

INCIDENT_FIELDS = ["name", "title", "incident_type", "severity", "status",
                   "is_security_incident", "affected_service", "affected_users",
                   "incident_manager", "detection_time", "reported_time", "containment_time",
                   "resolution_time", "problem", "ticket"]

PROBLEM_FIELDS = ["name", "title", "status", "priority", "category", "assigned_to",
                  "is_known_error", "incident_count", "root_cause", "workaround",
                  "permanent_fix", "change_request", "knowledge_article"]

CHANGE_FIELDS = ["name", "title", "change_type", "risk", "status", "priority", "requested_by",
                 "change_owner", "planned_start", "planned_end", "actual_start", "actual_end",
                 "approval_status", "cab_required", "validation_result", "ticket"]

PAR_FIELDS = ["name", "requester", "requested_for", "request_type", "status", "valid_from",
              "valid_till", "auto_revoke", "approval_status", "granted_on", "revoked_on"]


# ---------------------------------------------------------------------------
# incidents
# ---------------------------------------------------------------------------

@frappe.whitelist()
@api
def create_incident(title, incident_type, severity="S3 - Medium", **kwargs):
	if not utils.setting("enable_incident_management", 1):
		frappe.throw(_("Incident management is disabled."))

	doc = frappe.get_doc({
		"doctype": "Incident",
		"title": title,
		"incident_type": incident_type,
		"severity": severity,
		"status": kwargs.get("status") or "Open",
		"affected_service": kwargs.get("affected_service"),
		"affected_users": cint(kwargs.get("affected_users")),
		"business_impact": kwargs.get("business_impact"),
		"incident_manager": kwargs.get("incident_manager"),
		"ticket": kwargs.get("ticket"),
		"reported_by": kwargs.get("reported_by") or frappe.session.user,
	})
	doc.insert()
	if doc.ticket:
		frappe.db.set_value("Service Ticket", doc.ticket, "linked_incident", doc.name)
	frappe.db.commit()
	return ok(_fields(doc, INCIDENT_FIELDS), _("Incident created"))


@frappe.whitelist()
@api
def get_incident(incident):
	doc = frappe.get_doc("Incident", incident)
	doc.check_permission("read")
	return ok(_fields(doc, INCIDENT_FIELDS))


# ---------------------------------------------------------------------------
# problems
# ---------------------------------------------------------------------------

@frappe.whitelist()
@api
def create_problem(title, category=None, priority="Medium", description=None, ticket=None):
	if not utils.setting("enable_problem_management", 1):
		frappe.throw(_("Problem management is disabled."))

	doc = frappe.get_doc({
		"doctype": "Problem",
		"title": title,
		"category": category,
		"priority": priority,
		"description": description,
		"status": "Open",
	})
	if ticket:
		doc.append("related_records", {
			"reference_doctype": "Service Ticket",
			"reference_name": ticket,
			"relationship": "Caused By",
		})
	doc.insert()
	if ticket:
		frappe.db.set_value("Service Ticket", ticket, "linked_problem", doc.name)
	frappe.db.commit()
	return ok(_fields(doc, PROBLEM_FIELDS), _("Problem created"))


# ---------------------------------------------------------------------------
# changes
# ---------------------------------------------------------------------------

@frappe.whitelist()
@api
def create_change(title, change_type="Normal", risk="Medium", **kwargs):
	if not utils.setting("enable_change_management", 1):
		frappe.throw(_("Change management is disabled."))

	required = ("business_justification", "implementation_plan", "rollback_plan")
	missing = [f for f in required if not kwargs.get(f)]
	if missing:
		frappe.throw(_("Missing required fields: {0}").format(", ".join(missing)))

	doc = frappe.get_doc({
		"doctype": "Change Request",
		"title": title,
		"change_type": change_type,
		"risk": risk,
		"status": "Draft",
		"priority": kwargs.get("priority") or "Medium",
		"category": kwargs.get("category"),
		"requested_by": kwargs.get("requested_by") or frappe.session.user,
		"business_justification": kwargs["business_justification"],
		"implementation_plan": kwargs["implementation_plan"],
		"rollback_plan": kwargs["rollback_plan"],
		"testing_plan": kwargs.get("testing_plan"),
		"planned_start": kwargs.get("planned_start"),
		"planned_end": kwargs.get("planned_end"),
		"downtime_required": cint(kwargs.get("downtime_required")),
		"downtime_minutes": cint(kwargs.get("downtime_minutes")),
		"ticket": kwargs.get("ticket"),
	})
	doc.insert()
	if doc.ticket:
		frappe.db.set_value("Service Ticket", doc.ticket, "linked_change", doc.name)
	frappe.db.commit()
	return ok(_fields(doc, CHANGE_FIELDS), _("Change request created"))


@frappe.whitelist()
@api
def submit_change(change):
	doc = frappe.get_doc("Change Request", change)
	doc.check_permission("write")
	doc.status = "Submitted"
	doc.save()
	frappe.db.commit()
	return ok(_fields(doc, CHANGE_FIELDS), _("Change submitted for approval"))


# ---------------------------------------------------------------------------
# privileged access
# ---------------------------------------------------------------------------

@frappe.whitelist()
@api
def request_access(request_type, valid_from, valid_till, business_justification,
                   access_scope=None, requested_for=None, ticket=None):
	if not utils.setting("enable_privileged_access", 1):
		frappe.throw(_("Privileged access management is disabled."))

	scope = access_scope or [{"system": request_type, "access_level": "Admin"}]
	if isinstance(scope, str):
		scope = frappe.parse_json(scope)

	doc = frappe.get_doc({
		"doctype": "Privileged Access Request",
		"requester": frappe.session.user,
		"requested_for": requested_for or frappe.session.user,
		"request_type": request_type,
		"status": "Draft",
		"valid_from": valid_from,
		"valid_till": valid_till,
		"business_justification": business_justification,
		"ticket": ticket,
		"access_scope": scope,
	})
	doc.insert()
	doc.status = "Pending Approval"
	doc.save()
	frappe.db.commit()
	return ok(_fields(doc, PAR_FIELDS), _("Access request submitted"))


@frappe.whitelist()
@api
def revoke_access(request, reason):
	doc = frappe.get_doc("Privileged Access Request", request)
	doc.check_permission("write")
	doc.status = "Revoked"
	doc.revocation_reason = reason
	doc.save()
	frappe.db.commit()
	return ok(_fields(doc, PAR_FIELDS), _("Access revoked"))


# ---------------------------------------------------------------------------
# approvals and knowledge base
# ---------------------------------------------------------------------------

@frappe.whitelist()
@api
def approve(doctype, name, comments=None):
	return ok(approval.approve(doctype, name, comments), _("Approved"))


@frappe.whitelist()
@api
def reject(doctype, name, comments):
	return ok(approval.reject(doctype, name, comments), _("Rejected"))


@frappe.whitelist()
@api
def pending_approvals():
	return ok(approval.get_pending_approvals())


@frappe.whitelist()
@api
def search_knowledge(query=None, category=None, article_type=None, limit=20):
	return ok(knowledge.search(query, category, article_type, limit))


@frappe.whitelist()
@api
def get_article(article):
	doc = frappe.get_doc("Knowledge Article", article)
	doc.check_permission("read")
	knowledge.record_view(article)
	return ok({
		"name": doc.name, "title": doc.title, "article_type": doc.article_type,
		"category": doc.category, "content": doc.content, "video_url": doc.video_url,
		"version": doc.version, "helpful_count": doc.helpful_count,
		"not_helpful_count": doc.not_helpful_count, "modified": doc.modified,
	})


def _fields(doc, fields):
	return {field: doc.get(field) for field in fields}
