// Copyright (c) 2026, RSA and contributors
// For license information, please see license.txt

frappe.query_reports["Knowledge Base Usage"] = {
	filters: [

	{
		fieldname: "category",
		label: __("Category"),
		fieldtype: "Link",
		options: "IT Service Category",
	},
	],
};
