# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

"""Incident volume, severity mix and response timings, including security incidents."""

import frappe
from frappe import _

from turacoz_service_desk.turacoz_it_service_desk.report.report_utils import column


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		column(_("Incident"), "name", "Link", "Incident", 130),
		column(_("Title"), "title", "Data", width=240),
		column(_("Type"), "incident_type", "Data", width=140),
		column(_("Severity"), "severity", "Data", width=120),
		column(_("Status"), "status", "Data", width=110),
		column(_("Security"), "is_security_incident", "Check", width=90),
		column(_("Affected Service"), "affected_service", "Link", "Configuration Item", 170),
		column(_("Users Hit"), "affected_users", "Int", width=100),
		column(_("Detected"), "detection_time", "Datetime", width=150),
		column(_("Contained (h)"), "containment_hours", "Float", width=130, precision=1),
		column(_("Resolved (h)"), "resolution_hours", "Float", width=130, precision=1),
		column(_("Manager"), "incident_manager", "Link", "User", 150),
	]


def get_data(filters):
	clauses, values = [], []
	if filters.get("from_date"):
		clauses.append("i.creation >= %s")
		values.append(filters.from_date)
	if filters.get("to_date"):
		clauses.append("i.creation <= %s")
		values.append(str(filters.to_date) + " 23:59:59")
	if filters.get("severity"):
		clauses.append("i.severity = %s")
		values.append(filters.severity)
	if filters.get("incident_type"):
		clauses.append("i.incident_type = %s")
		values.append(filters.incident_type)
	if filters.get("security_only"):
		clauses.append("i.is_security_incident = 1")
	conditions = (" and " + " and ".join(clauses)) if clauses else ""

	return frappe.db.sql(
		f"""
		select i.name, i.title, i.incident_type, i.severity, i.status, i.is_security_incident,
			i.affected_service, i.affected_users, i.detection_time, i.incident_manager,
			round(timestampdiff(minute, i.detection_time, i.containment_time) / 60, 1)
				as containment_hours,
			round(timestampdiff(minute, i.detection_time, i.resolution_time) / 60, 1)
				as resolution_hours
		from `tabIncident` i
		where 1 = 1 {conditions}
		order by i.creation desc
		""",
		values, as_dict=True,
	)
