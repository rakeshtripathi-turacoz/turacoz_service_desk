# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime, time_diff_in_hours

from turacoz_service_desk.turacoz_it_service_desk.engine import sla, utils


class WorkLog(Document):
	def validate(self):
		self.engineer = self.engineer or frappe.session.user
		self.validate_times()
		self.set_hours()

	def validate_times(self):
		if self.end_time and self.start_time and self.end_time < self.start_time:
			frappe.throw(_("End time cannot be before start time."))

	def set_hours(self):
		if self.start_time and self.end_time:
			self.hours = flt(time_diff_in_hours(self.end_time, self.start_time), 2)
		elif not self.hours:
			self.hours = 0

	def on_update(self):
		self.sync_ticket()

	def on_trash(self):
		self.sync_ticket(removing=True)

	def sync_ticket(self, removing=False):
		if not self.ticket:
			return

		total = frappe.db.sql(
			"select sum(hours) from `tabWork Log` where ticket = %s and name != %s",
			(self.ticket, self.name),
		)[0][0] or 0
		if not removing:
			total = flt(total) + flt(self.hours)

		ticket = frappe.get_doc("Service Ticket", self.ticket)
		ticket.total_worked_hours = flt(total, 2)
		if not removing:
			utils.add_timeline(
				ticket, "Work Log",
				f"{self.activity_type or 'Work'} logged by {self.engineer} ({flt(self.hours, 2)}h)",
			)
			if not ticket.first_responded_on:
				sla.note_first_response(ticket, self.start_time)
		ticket.flags.ignore_permissions = True
		ticket.save(ignore_permissions=True)
