# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ITServiceCategory(Document):
	def validate(self):
		self.validate_cycle()
		self.validate_group()

	def validate_cycle(self):
		parent, seen = self.parent_service_category, {self.name}
		while parent:
			if parent in seen:
				frappe.throw(_("Category hierarchy cannot contain a loop."))
			seen.add(parent)
			parent = frappe.db.get_value("IT Service Category", parent, "parent_service_category")

	def validate_group(self):
		if self.is_group:
			return
		has_children = frappe.db.exists("IT Service Category",
		                                {"parent_service_category": self.name})
		if has_children:
			self.is_group = 1

	def on_trash(self):
		if frappe.db.exists("IT Service Category", {"parent_service_category": self.name}):
			frappe.throw(_("Remove the sub categories first."))
