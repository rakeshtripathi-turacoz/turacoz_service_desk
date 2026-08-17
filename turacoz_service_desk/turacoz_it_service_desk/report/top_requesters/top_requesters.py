# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

"""Who raises the most tickets - useful for training and self service targeting."""

import frappe
from frappe import _

from turacoz_service_desk.turacoz_it_service_desk.report.report_utils import column, percent, ticket_conditions


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	return [
		column(_("Requester"), "requester", "Link", "User", 200),
		column(_("Department"), "department", "Link", "Department", 180),
		column(_("Tickets"), "total", "Int", width=90),
		column(_("Share %"), "share", "Percent", width=100),
		column(_("Incidents"), "incidents", "Int", width=100),
		column(_("Requests"), "requests", "Int", width=100),
		column(_("Open"), "open_tickets", "Int", width=90),
		column(_("Avg Rating"), "avg_rating", "Float", width=110, precision=2),
	]


def get_data(filters):
	conditions, values = ticket_conditions(filters, "t")
	rows = frappe.db.sql(
		f"""
		select t.requester, max(t.department) as department, count(t.name) as total,
			sum(case when t.ticket_type = 'Incident' then 1 else 0 end) as incidents,
			sum(case when t.ticket_type = 'Service Request' then 1 else 0 end) as requests,
			sum(case when t.status not in ('Resolved', 'Closed', 'Cancelled')
				then 1 else 0 end) as open_tickets,
			avg(t.feedback_rating) as avg_rating
		from `tabService Ticket` t
		where 1 = 1 {conditions}
		group by t.requester
		order by total desc
		limit 50
		""",
		values, as_dict=True,
	)

	grand_total = sum(row.total for row in rows)
	for row in rows:
		row.share = percent(row.total, grand_total)
		row.avg_rating = round((row.avg_rating or 0) * 5, 2)
	return rows
