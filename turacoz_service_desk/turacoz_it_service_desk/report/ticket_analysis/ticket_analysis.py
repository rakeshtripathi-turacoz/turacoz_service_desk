# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

"""Volume analysis by category, department, type, source or priority."""

import frappe
from frappe import _

from turacoz_service_desk.turacoz_it_service_desk.report.report_utils import column, percent, ticket_conditions

DIMENSIONS = {
	"Category": "t.category",
	"Sub Category": "t.sub_category",
	"Department": "t.department",
	"Ticket Type": "t.ticket_type",
	"Source": "t.source",
	"Priority": "t.priority",
	"Service": "t.service",
	"Configuration Item": "t.configuration_item",
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	dimension = filters.get("dimension") or "Category"
	data = get_data(filters, dimension)
	return get_columns(dimension), data, None, get_chart(data)


def get_columns(dimension):
	return [
		column(_(dimension), "dimension", "Data", width=200),
		column(_("Tickets"), "total", "Int", width=90),
		column(_("Share %"), "share", "Percent", width=100),
		column(_("Open"), "open_tickets", "Int", width=80),
		column(_("Resolved"), "resolved", "Int", width=90),
		column(_("SLA %"), "sla_compliance", "Percent", width=90),
		column(_("Avg Resolution (h)"), "avg_resolution_hours", "Float", width=160, precision=1),
		column(_("Avg Rating"), "avg_rating", "Float", width=110, precision=2),
	]


def get_data(filters, dimension):
	conditions, values = ticket_conditions(filters, "t")
	group_sql = DIMENSIONS.get(dimension, "t.category")

	rows = frappe.db.sql(
		f"""
		select {group_sql} as dimension,
			count(t.name) as total,
			sum(case when t.status not in ('Resolved', 'Closed', 'Cancelled')
				then 1 else 0 end) as open_tickets,
			sum(case when t.status in ('Resolved', 'Closed') then 1 else 0 end) as resolved,
			sum(case when t.resolution_sla_met = 1 then 1 else 0 end) as sla_met,
			avg(case when t.resolved_on is not null
				then timestampdiff(minute, t.opened_on, t.resolved_on) / 60 end)
				as avg_resolution_hours,
			avg(t.feedback_rating) as avg_rating
		from `tabService Ticket` t
		where 1 = 1 {conditions}
		group by dimension
		order by total desc
		""",
		values, as_dict=True,
	)

	grand_total = sum(row.total for row in rows)
	for row in rows:
		row.dimension = row.dimension or _("Not Set")
		row.share = percent(row.total, grand_total)
		row.sla_compliance = percent(row.sla_met, row.resolved)
		row.avg_resolution_hours = round(row.avg_resolution_hours or 0, 1)
		row.avg_rating = round((row.avg_rating or 0) * 5, 2)
	return rows


def get_chart(rows):
	top = rows[:10]
	return {
		"data": {"labels": [row.dimension for row in top],
		         "datasets": [{"name": _("Tickets"), "values": [row.total for row in top]}]},
		"type": "donut",
	}
