# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

"""Response and resolution SLA compliance, grouped by any dimension."""

import frappe
from frappe import _

from turacoz_service_desk.turacoz_it_service_desk.report.report_utils import column, percent, ticket_conditions

GROUPS = {
	"Priority": "t.priority",
	"Category": "t.category",
	"Team": "t.assigned_team",
	"Engineer": "t.assigned_engineer",
	"Department": "t.department",
	"Month": "date_format(t.opened_on, '%%Y-%%m')",
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	group_label = filters.get("group_by") or "Priority"
	return get_columns(group_label), get_data(filters, group_label), None, get_chart(
		get_data(filters, group_label), group_label
	)


def get_columns(group_label):
	return [
		column(_(group_label), "group_value", "Data", width=180),
		column(_("Tickets"), "total", "Int", width=90),
		column(_("Response Met"), "response_met", "Int", width=120),
		column(_("Response %"), "response_compliance", "Percent", width=120),
		column(_("Resolution Met"), "resolution_met", "Int", width=130),
		column(_("Resolution %"), "resolution_compliance", "Percent", width=130),
		column(_("Breached"), "breached", "Int", width=100),
		column(_("Avg Resolution (h)"), "avg_resolution_hours", "Float", width=160, precision=1),
	]


def get_data(filters, group_label):
	conditions, values = ticket_conditions(filters, "t")
	group_sql = GROUPS.get(group_label, "t.priority")

	rows = frappe.db.sql(
		f"""
		select {group_sql} as group_value,
			count(t.name) as total,
			sum(case when t.response_sla_met = 1 then 1 else 0 end) as response_met,
			sum(case when t.resolution_sla_met = 1 then 1 else 0 end) as resolution_met,
			sum(case when t.sla_status in ('Failed', 'Response Overdue', 'Resolution Overdue')
				then 1 else 0 end) as breached,
			avg(case when t.resolved_on is not null
				then timestampdiff(minute, t.opened_on, t.resolved_on) / 60 end)
				as avg_resolution_hours
		from `tabService Ticket` t
		where t.sla_policy is not null {conditions}
		group by group_value
		order by total desc
		""",
		values, as_dict=True,
	)

	for row in rows:
		row.group_value = row.group_value or _("Not Set")
		row.response_compliance = percent(row.response_met, row.total)
		row.resolution_compliance = percent(row.resolution_met, row.total)
		row.avg_resolution_hours = round(row.avg_resolution_hours or 0, 1)
	return rows


def get_chart(rows, group_label):
	return {
		"data": {
			"labels": [row.group_value for row in rows][:12],
			"datasets": [
				{"name": _("Response %"), "values": [row.response_compliance for row in rows][:12]},
				{"name": _("Resolution %"),
				 "values": [row.resolution_compliance for row in rows][:12]},
			],
		},
		"type": "bar",
		"colors": ["#5e64ff", "#28a745"],
	}
