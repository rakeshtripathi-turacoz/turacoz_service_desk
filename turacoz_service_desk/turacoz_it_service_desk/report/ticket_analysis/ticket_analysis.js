// Copyright (c) 2026, RSA and contributors
// For license information, please see license.txt

frappe.query_reports["Ticket Analysis"] = {
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
		fieldname: "status",
		label: __("Status"),
		fieldtype: "Select",
		options: ["", "Draft", "Open", "Assigned", "In Progress", "Pending User",
			"Pending Vendor", "Testing", "Resolved", "User Verification", "Closed",
			"Reopened", "Cancelled"].join("\n"),
	},
	{
		fieldname: "priority",
		label: __("Priority"),
		fieldtype: "Select",
		options: ["", "Low", "Medium", "High", "Critical"].join("\n"),
	},
	{
		fieldname: "ticket_type",
		label: __("Ticket Type"),
		fieldtype: "Select",
		options: ["", "Incident", "Service Request", "Change Request", "Problem",
			"Query"].join("\n"),
	},
	{
		fieldname: "category",
		label: __("Category"),
		fieldtype: "Link",
		options: "IT Service Category",
	},
	{
		fieldname: "department",
		label: __("Department"),
		fieldtype: "Link",
		options: "Department",
	},
	{
		fieldname: "assigned_team",
		label: __("Team"),
		fieldtype: "Link",
		options: "Service Desk Team",
	},
	{
		fieldname: "assigned_engineer",
		label: __("Engineer"),
		fieldtype: "Link",
		options: "User",
	},
	{
		fieldname: "dimension",
		label: __("Dimension"),
		fieldtype: "Select",
		options: ["Category", "Sub Category", "Department", "Ticket Type", "Source",
			"Priority", "Service", "Configuration Item"].join("\n"),
		default: "Category",
		reqd: 1,
	},
	],
};
