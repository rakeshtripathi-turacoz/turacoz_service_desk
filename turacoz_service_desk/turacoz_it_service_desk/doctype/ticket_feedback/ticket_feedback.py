# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from turacoz_service_desk.turacoz_it_service_desk.engine import utils


class TicketFeedback(Document):
	def validate(self):
		ticket = frappe.get_doc("Service Ticket", self.ticket)
		if ticket.status not in ("Resolved", "User Verification", "Closed"):
			frappe.throw(_("Feedback can only be given on a resolved or closed ticket."))
		self.requester = self.requester or ticket.requester
		self.submitted_on = self.submitted_on or now_datetime()

	def on_update(self):
		self.push_to_ticket()

	def push_to_ticket(self):
		ticket = frappe.get_doc("Service Ticket", self.ticket)
		ticket.feedback_rating = self.rating
		ticket.feedback_comments = self.comments
		utils.add_timeline(ticket, "Other", f"Feedback received ({round((self.rating or 0) * 5, 1)}/5)")
		ticket.flags.ignore_permissions = True
		ticket.save(ignore_permissions=True)
