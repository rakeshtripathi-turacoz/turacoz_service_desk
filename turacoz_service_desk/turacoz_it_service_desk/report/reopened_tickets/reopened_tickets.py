# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

"""Tickets the requester sent back - a quality signal."""

import frappe
from frappe import _

from turacoz_service_desk.turacoz_it_service_desk.report.report_utils import column, ticket_conditions


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	return [
		column(_("Ticket"), "name", "Link", "Service Ticket", 130),
		column(_("Subject"), "subject", "Data", width=240),
		column(_("Category"), "category", "Link", "IT Service Category", 140),
		column(_("Engineer"), "assigned_engineer", "Link", "User", 150),
		column(_("Reopens"), "reopen_count", "Int", width=90),
		column(_("Last Reopened"), "reopened_on", "Datetime", width=160),
		column(_("Status"), "status", "Data", width=110),
		column(_("Resolution Category"), "resolution_category", "Data", width=170),
		column(_("Rating"), "feedback_rating", "Float", width=90, precision=2),
	]


def get_data(filters):
	conditions, values = ticket_conditions(filters, "t")
	return frappe.db.sql(
		f"""
		select t.name, t.subject, t.category, t.assigned_engineer, t.reopen_count,
			t.reopened_on, t.status, t.resolution_category, t.feedback_rating
		from `tabService Ticket` t
		where ifnull(t.reopen_count, 0) > 0 {conditions}
		order by t.reopen_count desc, t.reopened_on desc
		""",
		values, as_dict=True,
	)
