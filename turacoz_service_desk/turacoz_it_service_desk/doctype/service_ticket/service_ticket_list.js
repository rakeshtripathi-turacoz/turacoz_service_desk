// Copyright (c) 2026, RSA and contributors
// For license information, please see license.txt

frappe.listview_settings["Service Ticket"] = {
	add_fields: ["status", "priority", "sla_status", "is_escalated", "resolution_by"],
	filters: [["status", "not in", ["Closed", "Cancelled"]]],

	get_indicator(doc) {
		const status_colour = {
			Draft: "grey",
			Open: "orange",
			Assigned: "blue",
			"In Progress": "blue",
			"Pending User": "yellow",
			"Pending Vendor": "yellow",
			Testing: "purple",
			Resolved: "green",
			"User Verification": "light-blue",
			Closed: "green",
			Reopened: "red",
			Cancelled: "grey",
		};

		if (
			["Response Overdue", "Resolution Overdue", "Failed"].includes(doc.sla_status) &&
			!["Closed", "Cancelled"].includes(doc.status)
		) {
			return [__("SLA Breached"), "red", "sla_status,in,Response Overdue|Resolution Overdue|Failed"];
		}

		return [__(doc.status), status_colour[doc.status] || "grey", "status,=," + doc.status];
	},

	formatters: {
		priority(value) {
			const colour = { Critical: "red", High: "orange", Medium: "blue", Low: "grey" }[value];
			return `<span class="indicator-pill ${colour}">${__(value || "")}</span>`;
		},
	},
};
