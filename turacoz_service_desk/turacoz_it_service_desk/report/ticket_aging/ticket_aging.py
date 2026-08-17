# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

"""How long open tickets have been waiting, bucketed."""

import frappe
from frappe import _

from turacoz_service_desk.turacoz_it_service_desk.report.report_utils import column, ticket_conditions

BUCKETS = [(1, "0 - 1 day"), (3, "1 - 3 days"), (7, "3 - 7 days"), (14, "7 - 14 days"),
           (30, "14 - 30 days")]


def execute(filters=None):
	data = get_data(filters)
	return get_columns(), data, None, get_chart(data)


def get_columns():
	return [
		column(_("Ticket"), "name", "Link", "Service Ticket", 130),
		column(_("Subject"), "subject", "Data", width=240),
		column(_("Status"), "status", "Data", width=110),
		column(_("Priority"), "priority", "Data", width=90),
		column(_("Engineer"), "assigned_engineer", "Link", "User", 150),
		column(_("Opened"), "opened_on", "Datetime", width=150),
		column(_("Age (days)"), "age_days", "Float", width=110, precision=1),
		column(_("Bucket"), "bucket", "Data", width=120),
		column(_("SLA"), "sla_status", "Data", width=120),
	]


def get_data(filters):
	conditions, values = ticket_conditions(filters, "t")
	rows = frappe.db.sql(
		f"""
		select t.name, t.subject, t.status, t.priority, t.assigned_engineer, t.opened_on,
			t.sla_status,
			round(timestampdiff(hour, t.opened_on, now()) / 24, 1) as age_days
		from `tabService Ticket` t
		where t.status not in ('Resolved', 'Closed', 'Cancelled') {conditions}
		order by age_days desc
		""",
		values, as_dict=True,
	)
	for row in rows:
		row.bucket = _bucket(row.age_days)
	return rows


def _bucket(age_days):
	for limit, label in BUCKETS:
		if age_days <= limit:
			return label
	return "30+ days"


def get_chart(rows):
	labels = [label for _limit, label in BUCKETS] + ["30+ days"]
	counts = {label: 0 for label in labels}
	for row in rows:
		counts[row["bucket"]] = counts.get(row["bucket"], 0) + 1
	return {
		"data": {"labels": labels, "datasets": [{"name": "Tickets",
		                                         "values": [counts[label] for label in labels]}]},
		"type": "bar",
	}
