# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class ServiceDeskSettings(Document):
	def validate(self):
		if cint(self.auto_close_after_days) < 0:
			frappe.throw(_("Auto close days cannot be negative."))
		if not 1 <= cint(self.reminder_before_breach_percent) <= 100:
			frappe.throw(_("The breach reminder threshold must be between 1 and 100."))
		if cint(self.audit_retention_days) < 0:
			frappe.throw(_("Audit retention days cannot be negative."))

	def on_update(self):
		frappe.clear_cache(doctype="Service Desk Settings")
