# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ServiceDeskAuditLog(Document):
	"""Append only. Audit rows may never be edited or deleted from the UI."""

	def on_update(self):
		if self.flags.ignore_permissions or frappe.flags.in_install:
			return
		if self.get_doc_before_save():
			frappe.throw(_("Audit log entries cannot be modified."))

	def on_trash(self):
		if frappe.flags.in_audit_purge:
			return
		if frappe.session.user != "Administrator":
			frappe.throw(_("Audit log entries cannot be deleted."))
