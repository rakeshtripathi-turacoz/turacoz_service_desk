# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ServiceDeskTeam(Document):
	def validate(self):
		self.validate_members()
		self.ensure_lead_is_member()

	def validate_members(self):
		seen = set()
		for row in self.members:
			if row.user in seen:
				frappe.throw(_("{0} is listed twice in this team.").format(row.user))
			seen.add(row.user)

	def ensure_lead_is_member(self):
		if not self.team_lead:
			return
		if any(row.user == self.team_lead for row in self.members):
			for row in self.members:
				if row.user == self.team_lead:
					row.role_in_team = "Lead"
			return
		self.append("members", {
			"user": self.team_lead, "role_in_team": "Lead", "is_available": 1,
			"max_open_tickets": 0,
		})

	@frappe.whitelist()
	def get_load(self):
		from turacoz_service_desk.turacoz_it_service_desk.engine.assignment import _open_counts

		users = [row.user for row in self.members]
		return _open_counts(users) if users else {}
