# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime, strip_html

from turacoz_service_desk.turacoz_it_service_desk.engine import approval, assignment, notification, sla, utils

ALLOWED_TRANSITIONS = {
	"Draft": {"Open", "Cancelled"},
	"Open": {"Assigned", "In Progress", "Pending User", "Pending Vendor", "Resolved", "Cancelled"},
	"Assigned": {"Open", "In Progress", "Pending User", "Pending Vendor", "Testing", "Resolved",
	             "Cancelled"},
	"In Progress": {"Assigned", "Pending User", "Pending Vendor", "Testing", "Resolved",
	                "Cancelled"},
	"Pending User": {"In Progress", "Assigned", "Resolved", "Closed", "Cancelled"},
	"Pending Vendor": {"In Progress", "Assigned", "Resolved", "Cancelled"},
	"Testing": {"In Progress", "Resolved", "User Verification", "Cancelled"},
	"Resolved": {"User Verification", "Closed", "Reopened", "In Progress"},
	"User Verification": {"Closed", "Reopened", "Resolved"},
	"Closed": {"Reopened"},
	"Reopened": {"Open", "Assigned", "In Progress", "Resolved", "Cancelled"},
	"Cancelled": set(),
}

WORK_STATUSES = ("In Progress", "Testing", "Resolved", "User Verification", "Closed")


class ServiceTicket(Document):
	# ------------------------------------------------------------------
	# lifecycle
	# ------------------------------------------------------------------

	def before_insert(self):
		self.opened_on = self.opened_on or now_datetime()
		self.requester = self.requester or frappe.session.user
		self.source = self.source or "Portal"
		if self.status == "Draft" and frappe.session.user != self.requester:
			self.status = "Open"

	def validate(self):
		self.previous = self.get_doc_before_save()
		self.previous_status = self.previous.status if self.previous else None
		self.previous_engineer = self.previous.assigned_engineer if self.previous else None

		self.set_defaults()
		self.set_priority()
		self.validate_status_transition()
		self.validate_resolution()
		self.handle_approval()
		self.route()
		self.apply_sla()
		self.stamp_dates()
		self.track_changes_on_timeline()

	def after_insert(self):
		assignment.sync_todo(self)
		notification.notify(self, "new_ticket")
		if self.approval_status == approval.PENDING:
			notification.notify(self, "approval_pending")
		elif self.assigned_engineer:
			notification.notify(self, "assignment", recipients=[self.assigned_engineer])

	def on_update(self):
		if self.flags.in_insert:
			return

		if self.assigned_engineer != self.previous_engineer:
			assignment.sync_todo(self, self.previous_engineer)
			if self.assigned_engineer:
				notification.notify(self, "assignment", recipients=[self.assigned_engineer])

		if self.previous_status and self.status != self.previous_status:
			self.notify_status_change()

	# ------------------------------------------------------------------
	# defaults and classification
	# ------------------------------------------------------------------

	def set_defaults(self):
		if self.service:
			service = frappe.get_cached_doc("Service Catalog", self.service)
			self.category = self.category or service.category
			self.sub_category = self.sub_category or service.sub_category
			self.priority = self.priority or service.default_priority
			self.department = self.department or service.department

		if self.category:
			category = frappe.get_cached_doc("IT Service Category", self.category)
			self.impact = self.impact or category.default_impact or "Medium"
			self.urgency = self.urgency or category.default_urgency or "Medium"

		if not self.requester_employee and self.requester:
			self.requester_employee = frappe.db.get_value(
				"Employee", {"user_id": self.requester, "status": "Active"}, "name"
			)
		if self.requester_employee and not self.department:
			self.department = frappe.db.get_value("Employee", self.requester_employee, "department")

		if not self.short_description and self.description:
			self.short_description = strip_html(self.description)[:140]

		if self.sub_category and self.category:
			parent = frappe.db.get_value("IT Service Category", self.sub_category,
			                             "parent_service_category")
			if parent and parent != self.category:
				frappe.throw(_("Sub category {0} does not belong to category {1}.")
				             .format(self.sub_category, self.category))

	def set_priority(self):
		"""Impact x urgency matrix, unless a user explicitly changed the priority."""
		if not utils.setting("derive_priority_from_impact_urgency", 1):
			return
		if self.previous and self.previous.priority != self.priority:
			return
		derived = utils.derive_priority(self.impact, self.urgency)
		if derived:
			self.priority = derived

	# ------------------------------------------------------------------
	# status
	# ------------------------------------------------------------------

	def validate_status_transition(self):
		if not self.previous_status or self.status == self.previous_status:
			return
		allowed = ALLOWED_TRANSITIONS.get(self.previous_status, set())
		if self.status not in allowed:
			frappe.throw(
				_("Cannot move a ticket from {0} to {1}.").format(
					_(self.previous_status), _(self.status)
				),
				title=_("Invalid Status Change"),
			)

	def validate_resolution(self):
		if self.status in ("Resolved", "Closed") and not self.resolution:
			frappe.throw(_("Add a resolution before marking the ticket {0}.").format(_(self.status)))
		if self.status == "Resolved" and not self.resolution_category:
			self.resolution_category = "Fixed"

	# ------------------------------------------------------------------
	# approval, routing, SLA
	# ------------------------------------------------------------------

	def handle_approval(self):
		if self.is_new():
			if approval.is_approval_required(self):
				approval.start(self)
			else:
				self.approval_status = approval.NOT_REQUIRED
			return

		if self.approval_status == approval.PENDING and self.status in WORK_STATUSES:
			frappe.throw(_("This ticket is waiting for approval and cannot move to {0}.")
			             .format(_(self.status)))
		if self.approval_status == approval.REJECTED and self.status not in (
			"Cancelled", "Closed", "Reopened", "Resolved"
		):
			frappe.throw(_("This request was rejected. Cancel or close the ticket."))

	def route(self):
		if self.status in ("Closed", "Cancelled", "Resolved"):
			return
		if self.approval_status == approval.PENDING:
			return
		assignment.auto_assign(self)

	def apply_sla(self):
		if self.is_new():
			sla.apply(self)
			return

		reapply = (
			self.previous
			and (self.previous.priority != self.priority or self.previous.category != self.category)
			and self.status not in ("Resolved", "Closed", "Cancelled")
		)
		if reapply:
			sla.apply(self, force=True)

		if self.previous_status and self.status != self.previous_status:
			if self.status in WORK_STATUSES and not self.first_responded_on:
				sla.note_first_response(self)
			sla.handle_status_change(self, self.previous_status)

	def stamp_dates(self):
		now = now_datetime()
		if self.status == "Resolved" and not self.resolved_on:
			self.resolved_on = now
		if self.status == "Closed" and not self.closed_on:
			self.closed_on = now
		if self.status == "Reopened" and self.previous_status != "Reopened":
			self.reopened_on = now
			self.reopen_count = cint(self.reopen_count) + 1
			self.closed_on = None

	# ------------------------------------------------------------------
	# timeline and notifications
	# ------------------------------------------------------------------

	def track_changes_on_timeline(self):
		if self.is_new():
			utils.add_timeline(self, "Created", f"Ticket raised by {self.requester}")
			return
		if self.previous_status and self.status != self.previous_status:
			utils.add_timeline(self, "Status Change", "Status updated",
			                   self.previous_status, self.status)
		if self.assigned_engineer != self.previous_engineer:
			utils.add_timeline(self, "Assignment", "Engineer changed",
			                   self.previous_engineer, self.assigned_engineer)

	def notify_status_change(self):
		event = {
			"Resolved": "resolution",
			"Closed": "closure",
			"Reopened": "reopened",
		}.get(self.status, "status_change")
		notification.notify(self, event)

	# ------------------------------------------------------------------
	# helpers used by the API layer
	# ------------------------------------------------------------------

	def add_watcher(self, user, notify_on="All Updates"):
		if any(row.user == user for row in self.watchers):
			return
		self.append("watchers", {"user": user, "notify_on": notify_on})


def get_permission_query_conditions(user=None):
	"""Employees only see their own tickets; service desk roles see everything."""
	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))
	privileged = {
		"System Manager", "Administrator", "IT Manager", "CISO", "Auditor",
		"Service Desk Executive", "Service Desk Engineer", "Service Desk Team Lead",
	}
	if roles & privileged:
		return ""
	user = frappe.db.escape(user)
	return (
		f"(`tabService Ticket`.requester = {user}"
		f" or `tabService Ticket`.requested_for = {user}"
		f" or `tabService Ticket`.owner = {user}"
		f" or `tabService Ticket`.assigned_engineer = {user})"
	)


def has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))
	privileged = {
		"System Manager", "Administrator", "IT Manager", "CISO", "Auditor",
		"Service Desk Executive", "Service Desk Engineer", "Service Desk Team Lead",
	}
	if roles & privileged:
		return True
	return user in (doc.requester, doc.requested_for, doc.owner, doc.assigned_engineer)
