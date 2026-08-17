# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

"""Shared filter and column helpers for the service desk reports."""

import frappe
from frappe.utils import flt

TICKET_FILTER_MAP = {
	"status": "status",
	"priority": "priority",
	"ticket_type": "ticket_type",
	"category": "category",
	"department": "department",
	"assigned_team": "assigned_team",
	"assigned_engineer": "assigned_engineer",
	"requester": "requester",
	"source": "source",
}


def ticket_conditions(filters, alias="t", date_field="creation"):
	"""(sql fragment, values) for the standard ticket filter set."""
	filters = frappe._dict(filters or {})
	clauses, values = [], []

	if filters.get("from_date"):
		clauses.append(f"{alias}.{date_field} >= %s")
		values.append(filters.from_date)
	if filters.get("to_date"):
		clauses.append(f"{alias}.{date_field} <= %s")
		values.append(str(filters.to_date) + " 23:59:59")

	for key, column in TICKET_FILTER_MAP.items():
		value = filters.get(key)
		if not value:
			continue
		if isinstance(value, (list, tuple)):
			placeholders = ", ".join(["%s"] * len(value))
			clauses.append(f"{alias}.{column} in ({placeholders})")
			values.extend(value)
		else:
			clauses.append(f"{alias}.{column} = %s")
			values.append(value)

	return (" and " + " and ".join(clauses) if clauses else ""), values


def percent(part, total, digits=1):
	return round(flt(part) / flt(total) * 100, digits) if total else 0.0


def column(label, fieldname, fieldtype="Data", options=None, width=120, precision=None):
	col = {"label": label, "fieldname": fieldname, "fieldtype": fieldtype, "width": width}
	if options:
		col["options"] = options
	if precision:
		col["precision"] = precision
	return col
