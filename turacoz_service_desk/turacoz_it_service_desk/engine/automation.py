"""Scheduled automation: auto close, auto problem creation, access expiry, surveys."""

import frappe
from frappe.utils import add_days, add_to_date, cint, now_datetime, today

from turacoz_service_desk.turacoz_it_service_desk.engine import audit, notification, utils


# ---------------------------------------------------------------------------
# auto close resolved tickets
# ---------------------------------------------------------------------------

def auto_close_resolved_tickets():
	if not utils.setting("auto_close_enabled", 1):
		return

	days = cint(utils.setting("auto_close_after_days", 3)) or 3
	cutoff = add_to_date(now_datetime(), days=-days)

	tickets = frappe.get_all(
		"Service Ticket",
		filters={"status": ["in", ("Resolved", "User Verification")],
		         "resolved_on": ["<", cutoff]},
		pluck="name",
		limit_page_length=0,
	)
	for name in tickets:
		try:
			doc = frappe.get_doc("Service Ticket", name)
			doc.status = "Closed"
			doc.closed_on = now_datetime()
			utils.add_timeline(doc, "Status Change",
			                   f"Auto closed after {days} days without verification",
			                   "Resolved", "Closed")
			doc.save(ignore_permissions=True)
			audit.log("Service Ticket", name, "Status Changed", {"auto_close": True})
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Auto close failed for {name}")
	frappe.db.commit()


# ---------------------------------------------------------------------------
# satisfaction survey
# ---------------------------------------------------------------------------

def send_satisfaction_surveys():
	if not utils.setting("satisfaction_survey", 1):
		return

	since = add_days(today(), -1)
	tickets = frappe.get_all(
		"Service Ticket",
		filters={"status": "Closed", "closed_on": [">=", since], "feedback_rating": ["in", (0, None)]},
		fields=["name", "requester"],
		limit_page_length=0,
	)
	for row in tickets:
		if frappe.db.exists("Ticket Feedback", {"ticket": row.name}):
			continue
		doc = frappe.get_doc("Service Ticket", row.name)
		notification.notify(doc, "feedback_request", recipients=[row.requester])
	frappe.db.commit()


# ---------------------------------------------------------------------------
# auto problem creation from repeating incidents
# ---------------------------------------------------------------------------

def auto_create_problems():
	threshold = cint(utils.setting("auto_create_problem_threshold", 5))
	if threshold <= 0 or not utils.setting("enable_problem_management", 1):
		return

	since = add_days(today(), -30)
	rows = frappe.db.sql(
		"""
		select category, count(name) as total
		from `tabService Ticket`
		where ticket_type = 'Incident'
			and creation >= %s
			and ifnull(linked_problem, '') = ''
			and ifnull(category, '') != ''
		group by category
		having total >= %s
		""",
		(since, threshold),
		as_dict=True,
	)

	for row in rows:
		open_problem = frappe.db.exists("Problem", {
			"category": row.category,
			"status": ["not in", ("Resolved", "Closed")],
		})
		if open_problem:
			problem = open_problem
		else:
			doc = frappe.get_doc({
				"doctype": "Problem",
				"title": f"Recurring incidents in {row.category}",
				"status": "Open",
				"priority": "High",
				"category": row.category,
				"identified_on": today(),
				"description": (
					f"{row.total} incidents were raised for {row.category} in the last 30 days. "
					"Automatically created by the service desk automation engine."
				),
			})
			doc.insert(ignore_permissions=True)
			problem = doc.name
			audit.log("Problem", problem, "Created", {"auto": True, "category": row.category})

		tickets = frappe.get_all(
			"Service Ticket",
			filters={"ticket_type": "Incident", "category": row.category,
			         "creation": [">=", since], "linked_problem": ["in", ("", None)]},
			pluck="name",
			limit_page_length=0,
		)
		for ticket in tickets:
			frappe.db.set_value("Service Ticket", ticket, "linked_problem", problem,
			                    update_modified=False)
		frappe.db.set_value("Problem", problem, "incident_count", len(tickets))
	frappe.db.commit()


# ---------------------------------------------------------------------------
# privileged access expiry
# ---------------------------------------------------------------------------

def expire_privileged_access():
	if not utils.setting("enable_privileged_access", 1):
		return

	now = now_datetime()
	requests = frappe.get_all(
		"Privileged Access Request",
		filters={"status": ["in", ("Approved", "Active")], "valid_till": ["<", now]},
		fields=["name", "auto_revoke"],
		limit_page_length=0,
	)
	for row in requests:
		doc = frappe.get_doc("Privileged Access Request", row.name)
		if doc.auto_revoke:
			doc.status = "Revoked"
			doc.revoked_by = "Administrator"
			doc.revoked_on = now
			doc.revocation_reason = "Automatically revoked on expiry"
			audit.log(doc.doctype, doc.name, "Access Revoked", {"auto": True})
			notification.notify(doc, "access_revoked")
		else:
			doc.status = "Expired"
		doc.save(ignore_permissions=True)
	frappe.db.commit()


def notify_expiring_access():
	"""Warn one day before privileged access lapses."""
	if not utils.setting("enable_privileged_access", 1):
		return

	window_start = now_datetime()
	window_end = add_to_date(window_start, days=1)
	requests = frappe.get_all(
		"Privileged Access Request",
		filters={"status": ["in", ("Approved", "Active")],
		         "valid_till": ["between", (window_start, window_end)]},
		pluck="name",
		limit_page_length=0,
	)
	for name in requests:
		notification.notify(frappe.get_doc("Privileged Access Request", name), "access_expiring")


# ---------------------------------------------------------------------------
# scheduler entry points
# ---------------------------------------------------------------------------

def every_fifteen_minutes():
	from turacoz_service_desk.turacoz_it_service_desk.engine import sla

	sla.check_breaches()


def hourly():
	from turacoz_service_desk.turacoz_it_service_desk.engine import sla

	sla.send_breach_reminders()
	expire_privileged_access()


def daily():
	auto_close_resolved_tickets()
	send_satisfaction_surveys()
	auto_create_problems()
	notify_expiring_access()
	audit.purge_expired()
