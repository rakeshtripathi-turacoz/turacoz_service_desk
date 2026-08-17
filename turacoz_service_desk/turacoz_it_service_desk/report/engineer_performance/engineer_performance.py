# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

"""Throughput, SLA and satisfaction per engineer."""

import frappe
from frappe import _

from turacoz_service_desk.turacoz_it_service_desk.report.report_utils import column, percent, ticket_conditions


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	return [
		column(_("Engineer"), "assigned_engineer", "Link", "User", 180),
		column(_("Open"), "open_tickets", "Int", width=80),
		column(_("Resolved"), "resolved", "Int", width=90),
		column(_("Reopened"), "reopened", "Int", width=90),
		column(_("Reopen %"), "reopen_rate", "Percent", width=100),
		column(_("SLA Met"), "sla_met", "Int", width=90),
		column(_("SLA %"), "sla_compliance", "Percent", width=90),
		column(_("Avg Resolution (h)"), "avg_resolution_hours", "Float", width=160, precision=1),
		column(_("Logged Hours"), "logged_hours", "Float", width=120, precision=2),
		column(_("Avg Rating"), "avg_rating", "Float", width=110, precision=2),
	]


def get_data(filters):
	conditions, values = ticket_conditions(filters, "t")
	rows = frappe.db.sql(
		f"""
		select t.assigned_engineer,
			sum(case when t.status not in ('Resolved', 'Closed', 'Cancelled')
				then 1 else 0 end) as open_tickets,
			sum(case when t.status in ('Resolved', 'Closed') then 1 else 0 end) as resolved,
			sum(case when ifnull(t.reopen_count, 0) > 0 then 1 else 0 end) as reopened,
			sum(case when t.resolution_sla_met = 1 then 1 else 0 end) as sla_met,
			avg(case when t.resolved_on is not null
				then timestampdiff(minute, t.opened_on, t.resolved_on) / 60 end)
				as avg_resolution_hours,
			avg(t.feedback_rating) as avg_rating,
			count(t.name) as total
		from `tabService Ticket` t
		where ifnull(t.assigned_engineer, '') != '' {conditions}
		group by t.assigned_engineer
		order by resolved desc
		""",
		values, as_dict=True,
	)

	hours = dict(frappe.db.sql(
		"select engineer, sum(hours) from `tabWork Log` group by engineer"
	))

	for row in rows:
		row.sla_compliance = percent(row.sla_met, row.resolved)
		row.reopen_rate = percent(row.reopened, row.resolved)
		row.avg_resolution_hours = round(row.avg_resolution_hours or 0, 1)
		row.avg_rating = round((row.avg_rating or 0) * 5, 2)
		row.logged_hours = round(hours.get(row.assigned_engineer) or 0, 2)
	return rows
