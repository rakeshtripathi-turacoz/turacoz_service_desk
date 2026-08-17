# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from turacoz_service_desk.turacoz_it_service_desk.engine import audit


class Problem(Document):
	def validate(self):
		self.identified_on = self.identified_on or today()
		self.set_known_error()
		self.validate_closure()
		self.refresh_incident_count()

	def set_known_error(self):
		if self.status == "Known Error":
			self.is_known_error = 1
		if self.is_known_error and not self.workaround and self.status != "Resolved":
			frappe.msgprint(_("A known error should document a workaround."), indicator="orange",
			                alert=True)

	def validate_closure(self):
		if self.status in ("Resolved", "Closed"):
			if not self.root_cause:
				frappe.throw(_("Record the root cause before resolving a problem."))
			if not self.resolved_on:
				self.resolved_on = today()

	def refresh_incident_count(self):
		if self.is_new():
			return
		self.incident_count = frappe.db.count("Service Ticket", {"linked_problem": self.name})

	def on_update(self):
		if self.status in ("Resolved", "Closed") and self.permanent_fix:
			audit.log(self.doctype, self.name, "Modified", {"permanent_fix": True})
