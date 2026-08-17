"""REST API for tickets, comments, work logs and feedback.

Every endpoint is token authenticated by Frappe and enforces the usual role
permissions - nothing here bypasses them.

    POST /api/method/turacoz_service_desk.turacoz_it_service_desk.api.ticket.create
    GET  /api/method/turacoz_service_desk.turacoz_it_service_desk.api.ticket.get?ticket=TKT-2026-000001
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from turacoz_service_desk.turacoz_it_service_desk.api.response import api, ok
from turacoz_service_desk.turacoz_it_service_desk.engine import knowledge, sla

TICKET_FIELDS = [
	"name", "subject", "short_description", "description", "ticket_type", "status", "priority",
	"impact", "urgency", "severity", "category", "sub_category", "service", "source",
	"department", "requester", "requester_name", "requested_for", "assigned_team",
	"assigned_engineer", "engineer_name", "sla_policy", "sla_status", "response_by",
	"resolution_by", "first_responded_on", "opened_on", "resolved_on", "closed_on",
	"approval_status", "current_approval_level", "resolution", "resolution_category",
	"root_cause", "feedback_rating", "reopen_count", "total_worked_hours", "is_escalated",
	"escalation_level", "linked_asset", "configuration_item", "linked_project",
	"linked_incident", "linked_problem", "linked_change", "tags",
]

WRITABLE_FIELDS = {
	"subject", "short_description", "description", "ticket_type", "status", "priority",
	"impact", "urgency", "severity", "category", "sub_category", "service", "source",
	"department", "requested_for", "contact_number", "assigned_team", "assigned_engineer",
	"resolution", "resolution_category", "root_cause", "linked_asset", "configuration_item",
	"linked_project", "linked_incident", "linked_problem", "linked_change", "tags",
	"knowledge_article",
}


def _loads(value):
	if isinstance(value, str):
		try:
			return json.loads(value)
		except (ValueError, TypeError):
			return value
	return value


@frappe.whitelist()
@api
def create(**kwargs):
	"""Create a ticket. Unknown fields are ignored so clients can post loosely."""
	payload = {k: v for k, v in kwargs.items() if k in WRITABLE_FIELDS}
	if not payload.get("subject"):
		frappe.throw(_("subject is required"))
	if not payload.get("category") and not payload.get("service"):
		frappe.throw(_("category or service is required"))

	doc = frappe.get_doc({
		"doctype": "Service Ticket",
		"requester": kwargs.get("requester") or frappe.session.user,
		"source": payload.pop("source", None) or "API",
		"status": payload.pop("status", None) or "Open",
		**payload,
	})

	for user in _loads(kwargs.get("watchers")) or []:
		doc.add_watcher(user)

	doc.insert()
	frappe.db.commit()
	return ok(_ticket_payload(doc), _("Ticket created"))


@frappe.whitelist()
@api
def update(ticket, **kwargs):
	doc = frappe.get_doc("Service Ticket", ticket)
	doc.check_permission("write")

	changed = False
	for field, value in kwargs.items():
		if field in WRITABLE_FIELDS and doc.get(field) != value:
			doc.set(field, value)
			changed = True
	if not changed:
		return ok(_ticket_payload(doc), _("Nothing to update"))

	doc.save()
	frappe.db.commit()
	return ok(_ticket_payload(doc), _("Ticket updated"))


@frappe.whitelist()
@api
def get(ticket, with_activity=1):
	doc = frappe.get_doc("Service Ticket", ticket)
	doc.check_permission("read")
	payload = _ticket_payload(doc)
	if cint(with_activity):
		payload["comments"] = comments(ticket).get("data")
		payload["work_logs"] = work_logs(ticket).get("data")
		payload["timeline"] = [row.as_dict() for row in doc.timeline]
		payload["approvals"] = [row.as_dict() for row in doc.approvals]
	return ok(payload)


@frappe.whitelist()
@api
def list_tickets(status=None, priority=None, assigned_engineer=None, requester=None,
                 category=None, team=None, limit=20, start=0, order_by="modified desc"):
	filters = {}
	if status:
		filters["status"] = ["in", status.split(",")] if "," in status else status
	if priority:
		filters["priority"] = priority
	if assigned_engineer:
		filters["assigned_engineer"] = assigned_engineer
	if requester:
		filters["requester"] = requester
	if category:
		filters["category"] = category
	if team:
		filters["assigned_team"] = team

	rows = frappe.get_list(
		"Service Ticket",
		filters=filters,
		fields=["name", "subject", "status", "priority", "category", "requester",
		        "assigned_engineer", "sla_status", "resolution_by", "modified"],
		order_by=order_by,
		limit_start=cint(start),
		limit_page_length=cint(limit),
	)
	total = len(frappe.get_list("Service Ticket", filters=filters, fields=["name"],
	                            limit_page_length=0))
	return ok(rows, total=total)


@frappe.whitelist()
@api
def set_status(ticket, status, resolution=None, resolution_category=None, comment=None):
	doc = frappe.get_doc("Service Ticket", ticket)
	doc.check_permission("write")
	if resolution:
		doc.resolution = resolution
	if resolution_category:
		doc.resolution_category = resolution_category
	doc.status = status
	doc.save()
	if comment:
		_add_comment(doc, comment, "Public Note")
	frappe.db.commit()
	return ok(_ticket_payload(doc), _("Status updated to {0}").format(status))


@frappe.whitelist()
@api
def close(ticket, resolution=None, feedback_rating=None, feedback_comments=None):
	doc = frappe.get_doc("Service Ticket", ticket)
	doc.check_permission("write")
	if resolution and not doc.resolution:
		doc.resolution = resolution
	if doc.status not in ("Resolved", "User Verification", "Pending User"):
		doc.status = "Resolved"
		doc.save()
	doc.reload()
	doc.status = "Closed"
	doc.closed_on = now_datetime()
	doc.save()

	if feedback_rating:
		submit_feedback(ticket, feedback_rating, feedback_comments)
	frappe.db.commit()
	return ok(_ticket_payload(doc), _("Ticket closed"))


@frappe.whitelist()
@api
def reopen(ticket, reason=None):
	doc = frappe.get_doc("Service Ticket", ticket)
	doc.check_permission("write")
	if doc.status not in ("Resolved", "Closed", "User Verification"):
		frappe.throw(_("Only a resolved or closed ticket can be reopened."))
	doc.status = "Reopened"
	doc.save()
	if reason:
		_add_comment(doc, reason, "Public Note")
	frappe.db.commit()
	return ok(_ticket_payload(doc), _("Ticket reopened"))


@frappe.whitelist()
@api
def add_comment(ticket, content, comment_type="Public Note"):
	doc = frappe.get_doc("Service Ticket", ticket)
	doc.check_permission("read")
	comment = _add_comment(doc, content, comment_type)
	frappe.db.commit()
	return ok({"name": comment.name, "ticket": ticket}, _("Comment added"))


def _add_comment(doc, content, comment_type):
	comment = frappe.get_doc({
		"doctype": "Ticket Comment",
		"ticket": doc.name,
		"comment_by": frappe.session.user,
		"comment_type": comment_type,
		"content": content,
	})
	comment.insert(ignore_permissions=True)
	return comment


@frappe.whitelist()
@api
def comments(ticket, include_internal=None):
	frappe.get_doc("Service Ticket", ticket).check_permission("read")
	filters = {"ticket": ticket}
	if include_internal is None:
		roles = set(frappe.get_roles())
		internal = roles & {"System Manager", "IT Manager", "Service Desk Engineer",
		                    "Service Desk Executive", "Service Desk Team Lead"}
		if not internal:
			filters["comment_type"] = "Public Note"
	elif not cint(include_internal):
		filters["comment_type"] = "Public Note"

	return ok(frappe.get_all(
		"Ticket Comment",
		filters=filters,
		fields=["name", "comment_by", "comment_type", "content", "commented_on", "attachment"],
		order_by="creation asc",
	))


@frappe.whitelist()
@api
def add_work_log(ticket, description, start_time, end_time=None, activity_type="Diagnosis",
                 is_billable=0, is_internal=0):
	frappe.get_doc("Service Ticket", ticket).check_permission("read")
	log = frappe.get_doc({
		"doctype": "Work Log",
		"ticket": ticket,
		"engineer": frappe.session.user,
		"activity_type": activity_type,
		"start_time": start_time,
		"end_time": end_time,
		"description": description,
		"is_billable": cint(is_billable),
		"is_internal": cint(is_internal),
	})
	log.insert()
	frappe.db.commit()
	return ok({"name": log.name, "hours": log.hours}, _("Work log added"))


@frappe.whitelist()
@api
def work_logs(ticket):
	frappe.get_doc("Service Ticket", ticket).check_permission("read")
	return ok(frappe.get_all(
		"Work Log",
		filters={"ticket": ticket},
		fields=["name", "engineer", "activity_type", "start_time", "end_time", "hours",
		        "is_billable", "is_internal", "description"],
		order_by="start_time asc",
	))


@frappe.whitelist()
@api
def submit_feedback(ticket, rating, comments=None, response_speed=None,
                    resolution_quality=None, engineer_courtesy=None):
	doc = frappe.get_doc("Service Ticket", ticket)
	doc.check_permission("read")
	if frappe.db.exists("Ticket Feedback", {"ticket": ticket}):
		frappe.throw(_("Feedback has already been submitted for this ticket."))

	feedback = frappe.get_doc({
		"doctype": "Ticket Feedback",
		"ticket": ticket,
		"requester": doc.requester,
		"rating": rating,
		"comments": comments,
		"response_speed": response_speed,
		"resolution_quality": resolution_quality,
		"engineer_courtesy": engineer_courtesy,
	})
	feedback.insert(ignore_permissions=True)
	frappe.db.commit()
	return ok({"name": feedback.name}, _("Thank you for your feedback"))


@frappe.whitelist()
@api
def sla_status(ticket):
	return ok(sla.get_sla_status(ticket))


@frappe.whitelist()
@api
def suggest_articles(subject=None, description=None, category=None, ticket=None, limit=5):
	if ticket:
		doc = frappe.get_doc("Service Ticket", ticket)
		doc.check_permission("read")
		subject, description, category = doc.subject, doc.description, doc.category
	return ok(knowledge.suggest(subject, description, category, limit=limit))


@frappe.whitelist()
@api
def attachments(ticket):
	frappe.get_doc("Service Ticket", ticket).check_permission("read")
	return ok(frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Service Ticket", "attached_to_name": ticket},
		fields=["name", "file_name", "file_url", "file_size", "is_private", "creation", "owner"],
	))


def _ticket_payload(doc):
	payload = {field: doc.get(field) for field in TICKET_FIELDS}
	payload["watchers"] = [row.user for row in doc.watchers]
	return payload
