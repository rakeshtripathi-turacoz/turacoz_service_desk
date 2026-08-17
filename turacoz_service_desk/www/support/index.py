"""Employee self service portal for the Turacoz IT Service Desk (route: /support)."""

import frappe
from frappe import _

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to raise a request."), frappe.PermissionError)

	context.no_cache = 1
	context.title = _("IT Service Desk")
	context.parents = [{"title": _("My Account"), "route": "/me"}]

	context.categories = frappe.get_all(
		"IT Service Category",
		filters={"is_active": 1},
		fields=["name", "category_name", "is_group", "parent_service_category"],
		order_by="parent_service_category asc, category_name asc",
		limit_page_length=0,
	)
	context.services = frappe.get_all(
		"Service Catalog",
		filters={"is_active": 1},
		fields=["name", "service_name", "category", "sub_category", "default_priority",
		        "approval_required", "description"],
		order_by="service_name asc",
		limit_page_length=0,
	)
	context.tickets = frappe.get_list(
		"Service Ticket",
		filters={"requester": frappe.session.user},
		fields=["name", "subject", "status", "priority", "category", "sla_status",
		        "assigned_engineer", "resolution_by", "modified"],
		order_by="modified desc",
		limit_page_length=20,
	)
	context.open_count = frappe.db.count("Service Ticket", {
		"requester": frappe.session.user,
		"status": ["not in", ("Resolved", "Closed", "Cancelled")],
	})
	context.awaiting_me = frappe.db.count("Service Ticket", {
		"requester": frappe.session.user,
		"status": ["in", ("Pending User", "User Verification")],
	})
	context.articles = frappe.get_all(
		"Knowledge Article",
		filters={"status": "Published"},
		fields=["name", "title", "article_type", "category"],
		order_by="view_count desc",
		limit_page_length=6,
	)
	return context
