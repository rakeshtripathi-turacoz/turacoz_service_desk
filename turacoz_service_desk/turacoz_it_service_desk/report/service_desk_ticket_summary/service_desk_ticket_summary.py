# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

"""Operational ticket list with SLA state - the day to day service desk view."""

import frappe
from frappe import _

from turacoz_service_desk.turacoz_it_service_desk.report.report_utils import column, ticket_conditions


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	return [
		column(_("Ticket"), "name", "Link", "Service Ticket", 130),
		column(_("Subject"), "subject", "Data", width=240),
		column(_("Type"), "ticket_type", "Data", width=110),
		column(_("Status"), "status", "Data", width=110),
		column(_("Priority"), "priority", "Data", width=90),
		column(_("Category"), "category", "Link", "IT Service Category", 130),
		column(_("Requester"), "requester", "Link", "User", 150),
		column(_("Team"), "assigned_team", "Link", "Service Desk Team", 130),
		column(_("Engineer"), "assigned_engineer", "Link", "User", 150),
		column(_("SLA"), "sla_status", "Data", width=120),
		column(_("Resolve By"), "resolution_by", "Datetime", width=150),
		column(_("Opened"), "opened_on", "Datetime", width=150),
		column(_("Resolved"), "resolved_on", "Datetime", width=150),
		column(_("Age (h)"), "age_hours", "Float", width=90, precision=1),
		column(_("Worked (h)"), "total_worked_hours", "Float", width=100, precision=2),
	]


def get_data(filters):
	conditions, values = ticket_conditions(filters, "t")
	return frappe.db.sql(
		f"""
		select t.name, t.subject, t.ticket_type, t.status, t.priority, t.category,
			t.requester, t.assigned_team, t.assigned_engineer, t.sla_status,
			t.resolution_by, t.opened_on, t.resolved_on, t.total_worked_hours,
			round(timestampdiff(minute, t.opened_on,
				coalesce(t.resolved_on, now())) / 60, 1) as age_hours
		from `tabService Ticket` t
		where 1 = 1 {conditions}
		order by field(t.priority, 'Critical', 'High', 'Medium', 'Low'), t.opened_on
		""",
		values, as_dict=True,
	)
