"""Dashboard metrics for the employee, engineer, manager and executive views (PRD module 16)."""

import frappe
from frappe.utils import add_days, cint, flt, getdate, now_datetime, today

from turacoz_service_desk.turacoz_it_service_desk.api.response import api, ok
from turacoz_service_desk.turacoz_it_service_desk.engine import approval

OPEN = ["not in", ("Resolved", "Closed", "Cancelled")]


@frappe.whitelist()
@api
def employee(user=None):
	user = user or frappe.session.user
	base = {"requester": user}
	return ok({
		"open": frappe.db.count("Service Ticket", {**base, "status": OPEN}),
		"pending_with_me": frappe.db.count(
			"Service Ticket", {**base, "status": ["in", ("Pending User", "User Verification")]}
		),
		"resolved_this_month": frappe.db.count("Service Ticket", {
			**base, "status": ["in", ("Resolved", "Closed")],
			"resolved_on": [">=", _month_start()],
		}),
		"awaiting_my_approval": len(approval.get_pending_approvals(user)),
		"recent": frappe.get_all(
			"Service Ticket", filters=base,
			fields=["name", "subject", "status", "priority", "sla_status", "modified"],
			order_by="modified desc", limit=10,
		),
		"popular_articles": frappe.get_all(
			"Knowledge Article", filters={"status": "Published"},
			fields=["name", "title", "article_type", "view_count"],
			order_by="view_count desc", limit=5,
		),
	})


@frappe.whitelist()
@api
def engineer(user=None):
	user = user or frappe.session.user
	base = {"assigned_engineer": user}
	overdue = frappe.db.count("Service Ticket", {
		**base, "status": OPEN, "resolution_by": ["<", now_datetime()],
	})
	closed = frappe.get_all(
		"Service Ticket",
		filters={**base, "status": ["in", ("Resolved", "Closed")],
		         "resolved_on": [">=", _month_start()]},
		fields=["resolution_sla_met", "feedback_rating"],
	)
	met = len([t for t in closed if t.resolution_sla_met])
	rated = [flt(t.feedback_rating) for t in closed if t.feedback_rating]

	return ok({
		"assigned": frappe.db.count("Service Ticket", {**base, "status": OPEN}),
		"in_progress": frappe.db.count("Service Ticket", {**base, "status": "In Progress"}),
		"due_today": frappe.db.count("Service Ticket", {
			**base, "status": OPEN,
			"resolution_by": ["between", (today() + " 00:00:00", today() + " 23:59:59")],
		}),
		"overdue": overdue,
		"resolved_this_month": len(closed),
		"sla_compliance": round(met / len(closed) * 100, 1) if closed else 100.0,
		"average_rating": round(sum(rated) / len(rated) * 5, 2) if rated else None,
		"hours_this_week": flt(frappe.db.sql(
			"select sum(hours) from `tabWork Log` where engineer = %s and start_time >= %s",
			(user, add_days(today(), -7)),
		)[0][0] or 0, 2),
		"queue": frappe.get_all(
			"Service Ticket", filters={**base, "status": OPEN},
			fields=["name", "subject", "status", "priority", "sla_status", "resolution_by"],
			order_by="field(priority, 'Critical', 'High', 'Medium', 'Low'), resolution_by asc",
			limit=15,
		),
	})


@frappe.whitelist()
@api
def manager(team=None, days=30):
	since = add_days(today(), -cint(days))
	filters = {"assigned_team": team} if team else {}

	by_status = frappe.get_all(
		"Service Ticket", filters={**filters, "status": OPEN},
		fields=["status", "count(name) as total"], group_by="status",
	)
	by_priority = frappe.get_all(
		"Service Ticket", filters={**filters, "status": OPEN},
		fields=["priority", "count(name) as total"], group_by="priority",
	)
	by_category = frappe.get_all(
		"Service Ticket", filters={**filters, "creation": [">=", since]},
		fields=["category", "count(name) as total"], group_by="category",
		order_by="total desc", limit=10,
	)
	by_department = frappe.get_all(
		"Service Ticket", filters={**filters, "creation": [">=", since]},
		fields=["department", "count(name) as total"], group_by="department",
		order_by="total desc", limit=10,
	)

	resolved = frappe.get_all(
		"Service Ticket",
		filters={**filters, "status": ["in", ("Resolved", "Closed")],
		         "resolved_on": [">=", since]},
		fields=["resolution_sla_met", "response_sla_met", "reopen_count"],
	)
	total = len(resolved)

	return ok({
		"open_total": frappe.db.count("Service Ticket", {**filters, "status": OPEN}),
		"critical_open": frappe.db.count("Service Ticket",
		                                 {**filters, "status": OPEN, "priority": "Critical"}),
		"escalated": frappe.db.count("Service Ticket",
		                             {**filters, "status": OPEN, "is_escalated": 1}),
		"breached": frappe.db.count("Service Ticket", {
			**filters, "sla_status": ["in", ("Response Overdue", "Resolution Overdue", "Failed")],
			"creation": [">=", since],
		}),
		"unassigned": frappe.db.count("Service Ticket",
		                              {**filters, "status": OPEN, "assigned_engineer": ["in", ("", None)]}),
		"resolved": total,
		"sla_compliance": round(
			len([t for t in resolved if t.resolution_sla_met]) / total * 100, 1
		) if total else 100.0,
		"response_compliance": round(
			len([t for t in resolved if t.response_sla_met]) / total * 100, 1
		) if total else 100.0,
		"reopen_rate": round(
			len([t for t in resolved if cint(t.reopen_count)]) / total * 100, 1
		) if total else 0.0,
		"by_status": by_status,
		"by_priority": by_priority,
		"by_category": by_category,
		"by_department": by_department,
		"workload": frappe.get_all(
			"Service Ticket",
			filters={**filters, "status": OPEN, "assigned_engineer": ["is", "set"]},
			fields=["assigned_engineer", "count(name) as total"],
			group_by="assigned_engineer", order_by="total desc",
		),
	})


@frappe.whitelist()
@api
def executive(months=6):
	months = cint(months) or 6
	start = _month_start(months - 1)

	trend = frappe.db.sql(
		"""
		select date_format(creation, '%%Y-%%m') as month,
			count(name) as raised,
			sum(case when status in ('Resolved', 'Closed') then 1 else 0 end) as resolved,
			sum(case when resolution_sla_met = 1 then 1 else 0 end) as sla_met
		from `tabService Ticket`
		where creation >= %s
		group by month order by month
		""",
		(start,), as_dict=True,
	)

	changes = frappe.db.sql(
		"""
		select validation_result, count(name) as total
		from `tabChange Request`
		where creation >= %s and status in ('Completed', 'Closed', 'Rolled Back')
		group by validation_result
		""",
		(start,), as_dict=True,
	)
	change_total = sum(cint(row.total) for row in changes) or 0
	change_success = sum(cint(row.total) for row in changes
	                     if row.validation_result in ("Successful", "Successful with Issues"))

	ratings = frappe.get_all(
		"Ticket Feedback", filters={"creation": [">=", start]}, fields=["rating"]
	)

	return ok({
		"trend": trend,
		"incidents": frappe.get_all(
			"Incident", filters={"creation": [">=", start]},
			fields=["severity", "count(name) as total"], group_by="severity",
		),
		"security_incidents": frappe.db.count(
			"Incident", {"is_security_incident": 1, "creation": [">=", start]}
		),
		"change_success_rate": round(change_success / change_total * 100, 1) if change_total else 100.0,
		"changes_completed": change_total,
		"customer_satisfaction": round(
			sum(flt(r.rating) for r in ratings) / len(ratings) * 5, 2
		) if ratings else None,
		"feedback_count": len(ratings),
		"open_problems": frappe.db.count("Problem", {"status": ["not in", ("Resolved", "Closed")]}),
		"active_privileged_access": frappe.db.count(
			"Privileged Access Request", {"status": ["in", ("Approved", "Active")]}
		),
		"knowledge_articles": frappe.db.count("Knowledge Article", {"status": "Published"}),
	})


@frappe.whitelist()
@api
def metrics():
	"""Single call powering the workspace number cards."""
	return ok({
		"employee": employee().get("data"),
		"engineer": engineer().get("data"),
		"manager": manager().get("data"),
	})


def _month_start(months_back=0):
	date = getdate(today())
	month = date.month - months_back
	year = date.year
	while month <= 0:
		month += 12
		year -= 1
	return f"{year}-{month:02d}-01"
