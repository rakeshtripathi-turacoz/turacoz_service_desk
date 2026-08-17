# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ConfigurationItem(Document):
	def validate(self):
		self.validate_relationships()
		self.validate_retirement()

	def validate_relationships(self):
		seen = set()
		for row in self.relationships:
			if row.configuration_item == self.name:
				frappe.throw(_("A configuration item cannot relate to itself."))
			key = (row.relationship_type, row.configuration_item)
			if key in seen:
				frappe.throw(_("Duplicate relationship {0} -> {1}.")
				             .format(row.relationship_type, row.configuration_item))
			seen.add(key)

	def validate_retirement(self):
		if self.status != "Retired":
			return
		open_tickets = frappe.db.count("Service Ticket", {
			"configuration_item": self.name,
			"status": ["not in", ("Resolved", "Closed", "Cancelled")],
		})
		if open_tickets:
			frappe.throw(_("{0} open tickets still reference this configuration item.")
			             .format(open_tickets))

	@frappe.whitelist()
	def get_open_tickets(self):
		return frappe.get_all(
			"Service Ticket",
			filters={"configuration_item": self.name,
			         "status": ["not in", ("Resolved", "Closed", "Cancelled")]},
			fields=["name", "subject", "status", "priority", "assigned_engineer"],
		)
