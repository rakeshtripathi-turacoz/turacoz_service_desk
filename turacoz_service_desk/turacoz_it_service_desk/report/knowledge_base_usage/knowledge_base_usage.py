# Copyright (c) 2026, RSA and contributors
# For license information, please see license.txt

"""Which articles are actually deflecting tickets."""

import frappe
from frappe import _

from turacoz_service_desk.turacoz_it_service_desk.report.report_utils import column, percent


def execute(filters=None):
	return get_columns(), get_data(frappe._dict(filters or {}))


def get_columns():
	return [
		column(_("Article"), "name", "Link", "Knowledge Article", 140),
		column(_("Title"), "title", "Data", width=260),
		column(_("Type"), "article_type", "Data", width=120),
		column(_("Category"), "category", "Link", "IT Service Category", 140),
		column(_("Status"), "status", "Data", width=100),
		column(_("Views"), "view_count", "Int", width=90),
		column(_("Helpful"), "helpful_count", "Int", width=90),
		column(_("Not Helpful"), "not_helpful_count", "Int", width=110),
		column(_("Helpful %"), "helpful_rate", "Percent", width=110),
		column(_("Used On Tickets"), "ticket_usage", "Int", width=140),
		column(_("Version"), "version", "Int", width=90),
	]


def get_data(filters):
	conditions, values = "", []
	if filters.get("category"):
		conditions = " and k.category = %s"
		values.append(filters.category)

	rows = frappe.db.sql(
		f"""
		select k.name, k.title, k.article_type, k.category, k.status, k.view_count,
			k.helpful_count, k.not_helpful_count, k.version
		from `tabKnowledge Article` k
		where 1 = 1 {conditions}
		order by k.view_count desc
		""",
		values, as_dict=True,
	)

	usage = dict(frappe.db.sql(
		"""
		select knowledge_article, count(name) from `tabService Ticket`
		where ifnull(knowledge_article, '') != '' group by knowledge_article
		"""
	))

	for row in rows:
		votes = (row.helpful_count or 0) + (row.not_helpful_count or 0)
		row.helpful_rate = percent(row.helpful_count, votes)
		row.ticket_usage = usage.get(row.name, 0)
	return rows
