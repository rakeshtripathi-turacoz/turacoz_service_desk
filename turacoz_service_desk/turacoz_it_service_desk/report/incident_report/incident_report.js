// Copyright (c) 2026, RSA and contributors
// For license information, please see license.txt

frappe.query_reports["Incident Report"] = {
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
		fieldname: "severity",
		label: __("Severity"),
		fieldtype: "Select",
		options: ["", "S1 - Critical", "S2 - High", "S3 - Medium", "S4 - Low"].join("\n"),
	},
	{
		fieldname: "incident_type",
		label: __("Incident Type"),
		fieldtype: "Select",
		options: ["", "Outage", "Degradation", "Security", "Data Breach", "Data Loss",
			"Malware", "Phishing", "Unauthorized Access", "Hardware Failure",
			"Other"].join("\n"),
	},
	{
		fieldname: "security_only",
		label: __("Security Incidents Only"),
		fieldtype: "Check",
	},
	],
};
