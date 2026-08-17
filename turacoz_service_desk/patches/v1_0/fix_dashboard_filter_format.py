"""Rewrite Number Card and Dashboard Chart filters into the desk filter format.

v1.0.0 stored them as [fieldname, operator, value]. The server side accepts that, but the
desk reads index 1 as the fieldname and shows "Invalid filter: not in" every time the
workspace is opened. The correct shape is [doctype, fieldname, operator, value, hidden].
"""

import frappe

MODULE = "Turacoz IT Service Desk"


def execute():
	from turacoz_service_desk.turacoz_it_service_desk.setup import desk

	if not frappe.db.exists("Module Def", MODULE):
		return

	desk.create_number_cards()
	desk.create_charts()

	# the "My Open Tickets" shortcut also shipped with a literal "user" value
	if frappe.db.exists("Workspace", desk.WORKSPACE):
		desk.create_workspace()

	frappe.db.commit()
