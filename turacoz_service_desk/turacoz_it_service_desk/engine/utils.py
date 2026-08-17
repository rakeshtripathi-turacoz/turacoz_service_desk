"""Shared helpers for the Turacoz IT Service Desk engines."""

import frappe
from frappe.utils import cint, get_datetime, now_datetime

SETTINGS = "Service Desk Settings"

OPEN_STATUSES = ("Draft", "Open", "Assigned", "In Progress", "Pending User",
                 "Pending Vendor", "Testing", "User Verification", "Reopened")
CLOSED_STATUSES = ("Resolved", "Closed", "Cancelled")

# impact x urgency -> priority (PRD module 1 / 18: auto priority)
PRIORITY_MATRIX = {
	("High", "High"): "Critical",
	("High", "Medium"): "High",
	("High", "Low"): "Medium",
	("Medium", "High"): "High",
	("Medium", "Medium"): "Medium",
	("Medium", "Low"): "Low",
	("Low", "High"): "Medium",
	("Low", "Medium"): "Low",
	("Low", "Low"): "Low",
}

PRIORITY_ORDER = ["Low", "Medium", "High", "Critical"]


def get_settings():
	"""Cached Service Desk Settings single."""
	return frappe.get_cached_doc(SETTINGS)


def setting(fieldname, default=None):
	value = frappe.db.get_single_value(SETTINGS, fieldname)
	return default if value is None else value


def derive_priority(impact, urgency):
	return PRIORITY_MATRIX.get((impact, urgency))


def raise_priority(priority):
	"""Bump a priority one step, capped at Critical."""
	try:
		idx = PRIORITY_ORDER.index(priority)
	except ValueError:
		return priority
	return PRIORITY_ORDER[min(idx + 1, len(PRIORITY_ORDER) - 1)]


def user_exists(user):
	return bool(user) and bool(frappe.db.exists("User", {"name": user, "enabled": 1}))


def get_users_with_role(role):
	"""Enabled, non system users holding a role."""
	return [
		u.parent
		for u in frappe.get_all(
			"Has Role",
			filters={"role": role, "parenttype": "User"},
			fields=["parent"],
		)
		if frappe.db.get_value("User", u.parent, "enabled")
	]


def get_employee(user):
	name = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")
	return frappe.get_cached_doc("Employee", name) if name else None


def get_reporting_manager(user):
	"""User id of the requester's reporting manager, via the Employee record."""
	employee = get_employee(user)
	if not employee or not employee.reports_to:
		return None
	return frappe.db.get_value("Employee", employee.reports_to, "user_id")


def get_department_head(department):
	if not department:
		return None
	meta = frappe.get_meta("Department")
	for fieldname in ("department_head", "head_of_department", "approver"):
		if meta.has_field(fieldname):
			head = frappe.db.get_value("Department", department, fieldname)
			if head:
				return frappe.db.get_value("Employee", head, "user_id") if \
					frappe.db.exists("Employee", head) else head
	return None


def add_timeline(doc, event_type, description, from_value=None, to_value=None, user=None):
	"""Append a row to a document's `timeline` child table when it has one."""
	if not doc.meta.has_field("timeline"):
		return
	doc.append("timeline", {
		"event_time": now_datetime(),
		"event_type": event_type,
		"user": user or frappe.session.user,
		"description": (description or "")[:500],
		"from_value": from_value,
		"to_value": to_value,
	})


def parse_datetime(value):
	return get_datetime(value) if value else None


def duration_seconds(value):
	"""Duration fields come back as float seconds."""
	return cint(value or 0)
