# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


class ApprovalMatrix(Document):
	def validate(self):
		self.validate_levels()
		self.validate_amounts()

	def validate_levels(self):
		if not self.levels:
			frappe.throw(_("Add at least one approval level."))

		seen = set()
		for row in sorted(self.levels, key=lambda level: cint(level.level)):
			if cint(row.level) <= 0:
				frappe.throw(_("Approval level must be a positive number."))
			if cint(row.level) in seen:
				frappe.throw(_("Level {0} is defined more than once.").format(row.level))
			seen.add(cint(row.level))

			if row.approver_type == "Role" and not row.approver_role:
				frappe.throw(_("Level {0}: select the approving role.").format(row.level))
			if row.approver_type == "Specific User" and not row.approver_user:
				frappe.throw(_("Level {0}: select the approving user.").format(row.level))
			if row.condition:
				try:
					compile(row.condition, "<approval condition>", "eval")
				except SyntaxError:
					frappe.throw(_("Level {0}: the condition is not a valid python expression.")
					             .format(row.level))

	def validate_amounts(self):
		if flt(self.min_amount) and flt(self.max_amount) and \
				flt(self.min_amount) > flt(self.max_amount):
			frappe.throw(_("Minimum amount cannot be greater than the maximum amount."))
