# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class SLAPolicy(Document):
	def validate(self):
		self.validate_priority_rules()
		self.validate_working_days()
		self.validate_escalation_rules()

	def validate_priority_rules(self):
		seen = set()
		for row in self.priority_rules:
			if row.priority in seen:
				frappe.throw(_("Priority {0} appears more than once.").format(row.priority))
			seen.add(row.priority)
			if cint(row.response_time) <= 0 or cint(row.resolution_time) <= 0:
				frappe.throw(_("Response and resolution times must be greater than zero for {0}.")
				             .format(row.priority))
			if cint(row.response_time) > cint(row.resolution_time):
				frappe.throw(_("Response time cannot exceed resolution time for {0}.")
				             .format(row.priority))

	def validate_working_days(self):
		if self.apply_24x7:
			return
		if not self.working_days:
			frappe.throw(_("Define business hours or mark the policy as 24x7."))
		for row in self.working_days:
			if row.start_time and row.end_time and str(row.end_time) <= str(row.start_time):
				frappe.throw(_("{0}: end time must be after start time.").format(row.workday))

	def validate_escalation_rules(self):
		for row in self.escalation_rules:
			if not row.escalate_to_role and not row.escalate_to_user:
				frappe.throw(_("Escalation rule {0} needs a role or a user.").format(row.idx))
			if not 1 <= cint(row.after_percent) <= 200:
				frappe.throw(_("Escalation threshold must be between 1 and 200 percent."))

	def on_update(self):
		if self.is_default:
			frappe.db.sql(
				"update `tabSLA Policy` set is_default = 0 where name != %s", (self.name,)
			)
