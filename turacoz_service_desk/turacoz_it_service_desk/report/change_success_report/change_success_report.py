# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

"""Change management outcomes, including rollbacks and emergency changes."""

import frappe
from frappe import _

from turacoz_service_desk.turacoz_it_service_desk.report.report_utils import column, percent


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, get_chart(data)


def get_columns():
	return [
		column(_("Change Type"), "change_type", "Data", width=140),
		column(_("Risk"), "risk", "Data", width=100),
		column(_("Total"), "total", "Int", width=90),
		column(_("Successful"), "successful", "Int", width=110),
		column(_("With Issues"), "with_issues", "Int", width=120),
		column(_("Failed"), "failed", "Int", width=90),
		column(_("Rolled Back"), "rolled_back", "Int", width=120),
		column(_("Success %"), "success_rate", "Percent", width=110),
		column(_("Avg Duration (h)"), "avg_duration_hours", "Float", width=150, precision=1),
	]


def get_data(filters):
	clauses, values = [], []
	if filters.get("from_date"):
		clauses.append("c.creation >= %s")
		values.append(filters.from_date)
	if filters.get("to_date"):
		clauses.append("c.creation <= %s")
		values.append(str(filters.to_date) + " 23:59:59")
	if filters.get("change_type"):
		clauses.append("c.change_type = %s")
		values.append(filters.change_type)
	conditions = (" and " + " and ".join(clauses)) if clauses else ""

	rows = frappe.db.sql(
		f"""
		select c.change_type, c.risk, count(c.name) as total,
			sum(case when c.validation_result = 'Successful' then 1 else 0 end) as successful,
			sum(case when c.validation_result = 'Successful with Issues' then 1 else 0 end)
				as with_issues,
			sum(case when c.validation_result = 'Failed' then 1 else 0 end) as failed,
			sum(case when c.validation_result = 'Rolled Back' or c.status = 'Rolled Back'
				then 1 else 0 end) as rolled_back,
			avg(case when c.actual_start is not null and c.actual_end is not null
				then timestampdiff(minute, c.actual_start, c.actual_end) / 60 end)
				as avg_duration_hours
		from `tabChange Request` c
		where c.status in ('Completed', 'Closed', 'Rolled Back') {conditions}
		group by c.change_type, c.risk
		order by total desc
		""",
		values, as_dict=True,
	)

	for row in rows:
		row.success_rate = percent(row.successful + row.with_issues, row.total)
		row.avg_duration_hours = round(row.avg_duration_hours or 0, 1)
	return rows


def get_chart(rows):
	return {
		"data": {
			"labels": [f"{row.change_type} / {row.risk}" for row in rows],
			"datasets": [{"name": _("Success %"), "values": [row.success_rate for row in rows]}],
		},
		"type": "bar",
	}
