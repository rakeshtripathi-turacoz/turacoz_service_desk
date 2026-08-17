// Copyright (c) 2026, RSA and contributors
// For license information, please see license.txt

frappe.query_reports["Change Success Report"] = {
	filters: [
	{
		fieldname: "from_date",
		label: __("From Date"),
		fieldtype: "Date",
		default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
	},
	{
		fieldname: "to_date",
		label: __("To Date"),
		fieldtype: "Date",
		default: frappe.datetime.get_today(),
	},
	{
		fieldname: "change_type",
		label: __("Change Type"),
		fieldtype: "Select",
		options: ["", "Standard", "Normal", "Emergency"].join("\n"),
	},
	],
};
