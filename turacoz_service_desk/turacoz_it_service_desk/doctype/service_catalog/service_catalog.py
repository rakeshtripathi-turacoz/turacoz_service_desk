# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ServiceCatalog(Document):
	def validate(self):
		if self.approval_required and not self.approval_matrix:
			default = frappe.db.get_value(
				"Approval Matrix", {"applies_to": "Service Ticket", "is_active": 1}, "name"
			)
			if not default:
				frappe.throw(_("Select an approval matrix for this service."))
			self.approval_matrix = default

		if self.sub_category:
			parent = frappe.db.get_value("IT Service Category", self.sub_category,
			                             "parent_service_category")
			if parent and parent != self.category:
				frappe.throw(_("Sub category {0} does not belong to {1}.")
				             .format(self.sub_category, self.category))
