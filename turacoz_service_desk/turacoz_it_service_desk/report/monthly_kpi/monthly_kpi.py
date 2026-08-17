# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

"""Month on month service desk KPIs for management reporting."""

import frappe
from frappe import _

from turacoz_service_desk.turacoz_it_service_desk.report.report_utils import column, percent, ticket_conditions


def execute(filters=None):
	data = get_data(filters)
	return get_columns(), data, None, get_chart(data)


def get_columns():
	return [
		column(_("Month"), "month", "Data", width=110),
		column(_("Raised"), "raised", "Int", width=90),
		column(_("Resolved"), "resolved", "Int", width=90),
		column(_("Closed"), "closed", "Int", width=90),
		column(_("Backlog"), "backlog", "Int", width=90),
		column(_("SLA %"), "sla_compliance", "Percent", width=90),
		column(_("First Response %"), "response_compliance", "Percent", width=150),
		column(_("Reopen %"), "reopen_rate", "Percent", width=100),
		column(_("Avg Resolution (h)"), "avg_resolution_hours", "Float", width=160, precision=1),
		column(_("Avg Rating"), "avg_rating", "Float", width=110, precision=2),
		column(_("Escalations"), "escalated", "Int", width=110),
	]


def get_data(filters):
	conditions, values = ticket_conditions(filters, "t")
	rows = frappe.db.sql(
		f"""
		select date_format(t.creation, '%%Y-%%m') as month,
			count(t.name) as raised,
			sum(case when t.status in ('Resolved', 'Closed') then 1 else 0 end) as resolved,
			sum(case when t.status = 'Closed' then 1 else 0 end) as closed,
			sum(case when t.status not in ('Resolved', 'Closed', 'Cancelled')
				then 1 else 0 end) as backlog,
			sum(case when t.resolution_sla_met = 1 then 1 else 0 end) as sla_met,
			sum(case when t.response_sla_met = 1 then 1 else 0 end) as response_met,
			sum(case when ifnull(t.reopen_count, 0) > 0 then 1 else 0 end) as reopened,
			sum(case when t.is_escalated = 1 then 1 else 0 end) as escalated,
			avg(case when t.resolved_on is not null
				then timestampdiff(minute, t.opened_on, t.resolved_on) / 60 end)
				as avg_resolution_hours,
			avg(t.feedback_rating) as avg_rating
		from `tabService Ticket` t
		where 1 = 1 {conditions}
		group by month
		order by month
		""",
		values, as_dict=True,
	)

	for row in rows:
		row.sla_compliance = percent(row.sla_met, row.resolved)
		row.response_compliance = percent(row.response_met, row.raised)
		row.reopen_rate = percent(row.reopened, row.resolved)
		row.avg_resolution_hours = round(row.avg_resolution_hours or 0, 1)
		row.avg_rating = round((row.avg_rating or 0) * 5, 2)
	return rows


def get_chart(rows):
	return {
		"data": {
			"labels": [row.month for row in rows],
			"datasets": [
				{"name": _("Raised"), "values": [row.raised for row in rows]},
				{"name": _("Resolved"), "values": [row.resolved for row in rows]},
			],
		},
		"type": "line",
	}
