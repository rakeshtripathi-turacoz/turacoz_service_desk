# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

"""Every ticket that missed a response or resolution deadline."""

import frappe
from frappe import _

from turacoz_service_desk.turacoz_it_service_desk.report.report_utils import column, ticket_conditions


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	return [
		column(_("Ticket"), "name", "Link", "Service Ticket", 130),
		column(_("Subject"), "subject", "Data", width=230),
		column(_("Priority"), "priority", "Data", width=90),
		column(_("Status"), "status", "Data", width=110),
		column(_("Engineer"), "assigned_engineer", "Link", "User", 150),
		column(_("Team"), "assigned_team", "Link", "Service Desk Team", 130),
		column(_("Breach Type"), "breach_type", "Data", width=130),
		column(_("Due"), "due_on", "Datetime", width=150),
		column(_("Actual"), "actual_on", "Datetime", width=150),
		column(_("Overdue By (h)"), "overdue_hours", "Float", width=130, precision=1),
		column(_("Escalated"), "is_escalated", "Check", width=90),
	]


def get_data(filters):
	conditions, values = ticket_conditions(filters, "t")
	rows = frappe.db.sql(
		f"""
		select t.name, t.subject, t.priority, t.status, t.assigned_engineer, t.assigned_team,
			t.response_by, t.resolution_by, t.first_responded_on, t.resolved_on,
			t.response_sla_met, t.resolution_sla_met, t.sla_status, t.is_escalated
		from `tabService Ticket` t
		where t.sla_policy is not null
			and (t.sla_status in ('Failed', 'Response Overdue', 'Resolution Overdue')
				or (t.resolution_by is not null and t.resolution_sla_met = 0
					and t.resolved_on is not null))
			{conditions}
		order by t.resolution_by
		""",
		values, as_dict=True,
	)

	out = []
	for row in rows:
		for kind, due, actual, met in (
			(_("Response"), row.response_by, row.first_responded_on, row.response_sla_met),
			(_("Resolution"), row.resolution_by, row.resolved_on, row.resolution_sla_met),
		):
			if not due or met:
				continue
			reference = actual or frappe.utils.now_datetime()
			if reference <= frappe.utils.get_datetime(due):
				continue
			out.append({
				**{k: row.get(k) for k in ("name", "subject", "priority", "status",
				                           "assigned_engineer", "assigned_team", "is_escalated")},
				"breach_type": kind,
				"due_on": due,
				"actual_on": actual,
				"overdue_hours": round(
					frappe.utils.time_diff_in_hours(reference, due), 1
				),
			})
	return out
