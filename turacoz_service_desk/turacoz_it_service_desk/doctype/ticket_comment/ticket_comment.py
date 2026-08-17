# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from turacoz_service_desk.turacoz_it_service_desk.engine import notification, sla, utils


class TicketComment(Document):
	def validate(self):
		self.comment_by = self.comment_by or frappe.session.user
		self.commented_on = self.commented_on or now_datetime()

	def after_insert(self):
		if not self.ticket:
			return

		ticket = frappe.get_doc("Service Ticket", self.ticket)
		utils.add_timeline(
			ticket, "Comment",
			f"{self.comment_type} by {self.comment_by}",
			user=self.comment_by,
		)

		is_requester = self.comment_by in (ticket.requester, ticket.requested_for)
		if not is_requester and not ticket.first_responded_on:
			sla.note_first_response(ticket, self.commented_on)

		ticket.flags.ignore_permissions = True
		ticket.save(ignore_permissions=True)

		if self.comment_type == "Public Note":
			recipients = None
			if is_requester:
				recipients = [u for u in (ticket.assigned_engineer,) if u]
			notification.notify(
				ticket, "comment", recipients=recipients,
				extra={"message": frappe.utils.strip_html(self.content or "")[:500]},
			)
