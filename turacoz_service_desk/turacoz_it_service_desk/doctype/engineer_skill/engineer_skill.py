# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class EngineerSkill(Document):
	def validate(self):
		duplicate = frappe.db.exists("Engineer Skill", {
			"engineer": self.engineer, "category": self.category, "name": ["!=", self.name],
		})
		if duplicate:
			frappe.throw(_("{0} already has a skill entry for {1}.")
			             .format(self.engineer, self.category))
