// Copyright (c) 2026, RSA and contributors
// For license information, please see license.txt

frappe.query_reports["Service Desk Ticket Summary"] = {
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
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "sla_status" && data) {
			const bad = ["Failed", "Response Overdue", "Resolution Overdue"];
			const colour = bad.includes(data.sla_status)
				? "red"
				: data.sla_status === "Fulfilled"
					? "green"
					: "orange";
			value = `<span style="color: var(--text-on-${colour}, ${colour})">${value}</span>`;
		}
		return value;
	},
};
