# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from turacoz_service_desk.turacoz_it_service_desk.engine import approval, notification, utils

APPROVAL_STATUSES = ("CAB Approval", "Risk Review")
IMPLEMENTATION_STATUSES = ("Scheduled", "Implementation", "Validation", "Completed", "Closed")


class ChangeRequest(Document):
	def validate(self):
		before = self.get_doc_before_save()
		self.previous_status = before.status if before else None

		self.set_defaults()
		self.validate_window()
		self.validate_risk()
		self.handle_approval()
		self.stamp_times()
		self.track_timeline()

	def set_defaults(self):
		self.requested_by = self.requested_by or frappe.session.user
		self.change_owner = self.change_owner or self.requested_by
		if self.risk in ("High", "Critical") or self.change_type == "Emergency":
			self.cab_required = 1

	def validate_window(self):
		if self.planned_start and self.planned_end and self.planned_end < self.planned_start:
			frappe.throw(_("Planned end cannot be before planned start."))
		if self.status in IMPLEMENTATION_STATUSES and not (self.planned_start and self.planned_end):
			frappe.throw(_("Set the implementation window before scheduling this change."))
		if self.downtime_required and self.status in IMPLEMENTATION_STATUSES \
				and not self.downtime_minutes:
			frappe.throw(_("Specify the expected downtime in minutes."))

	def validate_risk(self):
		if self.status in ("Completed", "Closed") and not self.validation_result:
			frappe.throw(_("Record the validation result before completing this change."))
		if self.validation_result == "Rolled Back" and not self.rollback_reason:
			frappe.throw(_("Explain why the change was rolled back."))

	def handle_approval(self):
		if self.is_new():
			self.approval_status = approval.NOT_REQUIRED
			return

		if self.previous_status == "Draft" and self.status == "Submitted":
			if approval.is_approval_required(self):
				approval.start(self)
				notification.notify(self, "approval_pending")
			return

		if self.status in IMPLEMENTATION_STATUSES and self.approval_status == approval.PENDING:
			frappe.throw(_("This change is still awaiting approval."))
		if self.approval_status == approval.REJECTED and self.status not in (
			"Rejected", "Cancelled", "Closed"
		):
			frappe.throw(_("This change was rejected. Move it to Rejected or Cancelled."))

	def stamp_times(self):
		now = now_datetime()
		if self.status == "Implementation" and not self.actual_start:
			self.actual_start = now
		if self.status in ("Validation", "Completed", "Closed", "Rolled Back") \
				and self.actual_start and not self.actual_end:
			self.actual_end = now

	def track_timeline(self):
		if self.is_new():
			utils.add_timeline(self, "Created", f"{self.change_type} change raised")
		elif self.previous_status and self.previous_status != self.status:
			utils.add_timeline(self, "Status Change", "Status updated",
			                   self.previous_status, self.status)

	def on_update(self):
		if self.approval_status == approval.APPROVED and self.status == "CAB Approval":
			frappe.db.set_value(self.doctype, self.name, "status", "Scheduled",
			                    update_modified=False)
