# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from turacoz_service_desk.turacoz_it_service_desk.engine import audit, notification, utils

SECURITY_TYPES = ("Security", "Data Breach", "Data Loss", "Malware", "Phishing",
                  "Unauthorized Access")


class Incident(Document):
	def validate(self):
		self.previous_status = (self.get_doc_before_save() or {}).get("status") \
			if self.get_doc_before_save() else None
		self.set_flags()
		self.stamp_times()
		self.validate_closure()
		self.track_timeline()

	def set_flags(self):
		if self.incident_type in SECURITY_TYPES:
			self.is_security_incident = 1
		self.reported_by = self.reported_by or frappe.session.user
		self.reported_time = self.reported_time or now_datetime()
		self.detection_time = self.detection_time or self.reported_time

	def stamp_times(self):
		now = now_datetime()
		if self.status == "Contained" and not self.containment_time:
			self.containment_time = now
		if self.status in ("Resolved", "Closed") and not self.resolution_time:
			self.resolution_time = now

	def validate_closure(self):
		if self.status in ("Resolved", "Closed"):
			if not self.resolution:
				frappe.throw(_("Record the resolution before closing an incident."))
			if self.severity in ("S1 - Critical", "S2 - High") and not self.root_cause:
				frappe.throw(_("A root cause analysis is mandatory for {0} incidents.")
				             .format(self.severity))

	def track_timeline(self):
		if self.is_new():
			utils.add_timeline(self, "Created", f"{self.incident_type} incident reported")
		elif self.previous_status and self.previous_status != self.status:
			utils.add_timeline(self, "Status Change", "Status updated",
			                   self.previous_status, self.status)

	def after_insert(self):
		if self.is_security_incident:
			recipients = utils.get_users_with_role("CISO")
			if recipients:
				notification.notify(self, "new_ticket", recipients=recipients)
			audit.log(self.doctype, self.name, "Created", {"security_incident": True})
