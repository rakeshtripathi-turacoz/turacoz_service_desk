# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime

from turacoz_service_desk.turacoz_it_service_desk.engine import approval, audit, notification


class PrivilegedAccessRequest(Document):
	def validate(self):
		before = self.get_doc_before_save()
		self.previous_status = before.status if before else None

		self.requester = self.requester or frappe.session.user
		self.validate_validity()
		self.handle_approval()
		self.handle_grant()

	def validate_validity(self):
		if self.valid_from and self.valid_till and \
				get_datetime(self.valid_till) <= get_datetime(self.valid_from):
			frappe.throw(_("Valid till must be after valid from."))
		if not self.access_scope:
			frappe.throw(_("List at least one system in the access scope."))

	def handle_approval(self):
		if self.is_new():
			self.approval_status = approval.PENDING if self.status != "Draft" \
				else approval.NOT_REQUIRED
			return

		if self.previous_status == "Draft" and self.status == "Pending Approval":
			approval.start(self)
			notification.notify(self, "approval_pending")
			return

		if self.status in ("Approved", "Active") and self.approval_status != approval.APPROVED:
			frappe.throw(_("Privileged access cannot be granted before every approval is in."))

	def handle_grant(self):
		now = now_datetime()
		if self.status in ("Approved", "Active") and not self.granted_on:
			self.granted_by = frappe.session.user
			self.granted_on = now
		if self.status == "Revoked" and not self.revoked_on:
			self.revoked_by = frappe.session.user
			self.revoked_on = now
			if not self.revocation_reason:
				frappe.throw(_("Record why the access was revoked."))

	def on_update(self):
		if self.previous_status == self.status:
			return
		if self.status in ("Approved", "Active"):
			audit.log(self.doctype, self.name, "Access Granted", {
				"systems": [row.system for row in self.access_scope],
				"valid_till": str(self.valid_till),
			})
			notification.notify(self, "access_granted")
		elif self.status in ("Revoked", "Expired"):
			audit.log(self.doctype, self.name, "Access Revoked", {"status": self.status})
			notification.notify(self, "access_revoked")
