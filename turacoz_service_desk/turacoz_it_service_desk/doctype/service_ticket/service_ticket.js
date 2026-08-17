// Copyright (c) 2026, RSA and contributors
// For license information, please see license.txt

const ENGINE = "turacoz_service_desk.turacoz_it_service_desk.engine";
const CLOSED = ["Resolved", "Closed", "Cancelled"];

frappe.ui.form.on("Service Ticket", {
	setup(frm) {
		frm.set_query("sub_category", () => ({
			filters: { parent_service_category: frm.doc.category || "" },
		}));
		frm.set_query("service", () => ({ filters: { is_active: 1 } }));
		frm.set_query("assigned_team", () => ({ filters: { is_active: 1 } }));
	},

	refresh(frm) {
		if (frm.is_new()) return;

		show_sla(frm);
		show_approval(frm);
		add_actions(frm);
	},

	category(frm) {
		if (frm.doc.sub_category) frm.set_value("sub_category", null);
	},
});

function show_sla(frm) {
	if (!frm.doc.sla_policy || CLOSED.includes(frm.doc.status)) {
		if (frm.doc.sla_status) {
			frm.dashboard.add_indicator(
				__("SLA: {0}", [frm.doc.sla_status]),
				frm.doc.sla_status === "Fulfilled" ? "green" : "red"
			);
		}
		return;
	}

	frappe.call({
		method: `${ENGINE}.sla.get_sla_status`,
		args: { ticket: frm.doc.name },
		callback({ message }) {
			if (!message) return;
			const colour = (pct) => (pct >= 100 ? "red" : pct >= 75 ? "orange" : "green");

			if (!frm.doc.first_responded_on && message.response_remaining_seconds !== null) {
				frm.dashboard.add_indicator(
					__("Respond in {0}", [format_duration(message.response_remaining_seconds)]),
					colour(message.response_percent)
				);
			}
			if (message.resolution_remaining_seconds !== null) {
				frm.dashboard.add_indicator(
					__("Resolve in {0}", [format_duration(message.resolution_remaining_seconds)]),
					colour(message.resolution_percent)
				);
			}
			if (message.is_escalated) {
				frm.dashboard.add_indicator(
					__("Escalated (L{0})", [message.escalation_level]),
					"red"
				);
			}
		},
	});
}

function format_duration(seconds) {
	const overdue = seconds < 0;
	const total = Math.abs(Math.round(seconds));
	const hours = Math.floor(total / 3600);
	const minutes = Math.floor((total % 3600) / 60);
	const label = hours ? `${hours}h ${minutes}m` : `${minutes}m`;
	return overdue ? __("{0} overdue", [label]) : label;
}

function show_approval(frm) {
	if (frm.doc.approval_status !== "Pending") return;

	frappe.call({
		method: `${ENGINE}.approval.get_approval_state`,
		args: { doctype: frm.doc.doctype, name: frm.doc.name },
		callback({ message }) {
			if (!message) return;
			frm.dashboard.add_indicator(
				__("Approval pending (level {0})", [message.level]),
				"orange"
			);
			if (!message.can_action) return;

			frm.add_custom_button(__("Approve"), () => approval_action(frm, "approve"))
				.addClass("btn-primary");
			frm.add_custom_button(__("Reject"), () => approval_action(frm, "reject"));
		},
	});
}

function approval_action(frm, action) {
	const reject = action === "reject";
	frappe.prompt(
		[
			{
				fieldname: "comments",
				label: __("Comments"),
				fieldtype: "Small Text",
				reqd: reject ? 1 : 0,
			},
		],
		({ comments }) => {
			frappe.call({
				method: `${ENGINE}.approval.${action}`,
				args: { doctype: frm.doc.doctype, name: frm.doc.name, comments },
				freeze: true,
				callback: () => frm.reload_doc(),
			});
		},
		reject ? __("Reject Ticket") : __("Approve Ticket"),
		reject ? __("Reject") : __("Approve")
	);
}

function add_actions(frm) {
	if (!CLOSED.includes(frm.doc.status)) {
		frm.add_custom_button(__("Reassign"), () => reassign(frm), __("Actions"));
		frm.add_custom_button(__("Add Work Log"), () => add_work_log(frm), __("Actions"));
	}

	frm.add_custom_button(__("Suggest Articles"), () => suggest(frm), __("Actions"));

	if (frm.doc.resolution && !frm.doc.knowledge_article) {
		frm.add_custom_button(__("Create Knowledge Article"), () => {
			frappe.call({
				method: `${ENGINE}.knowledge.create_article_from_ticket`,
				args: { ticket: frm.doc.name },
				freeze: true,
				callback({ message }) {
					frappe.set_route("Form", "Knowledge Article", message);
				},
			});
		}, __("Create"));
	}

	if (!frm.doc.linked_incident) {
		frm.add_custom_button(__("Incident"), () => make_linked(frm, "Incident"), __("Create"));
	}
	if (!frm.doc.linked_problem) {
		frm.add_custom_button(__("Problem"), () => make_linked(frm, "Problem"), __("Create"));
	}
	if (!frm.doc.linked_change) {
		frm.add_custom_button(__("Change Request"), () => make_linked(frm, "Change Request"),
			__("Create"));
	}
}

function reassign(frm) {
	frappe.prompt(
		[
			{
				fieldname: "team",
				label: __("Team"),
				fieldtype: "Link",
				options: "Service Desk Team",
				default: frm.doc.assigned_team,
			},
			{
				fieldname: "engineer",
				label: __("Engineer"),
				fieldtype: "Link",
				options: "User",
				description: __("Leave blank to let the assignment engine choose."),
			},
			{ fieldname: "reason", label: __("Reason"), fieldtype: "Small Text" },
		],
		(values) => {
			frappe.call({
				method: `${ENGINE}.assignment.reassign`,
				args: { ticket: frm.doc.name, ...values },
				freeze: true,
				callback: () => frm.reload_doc(),
			});
		},
		__("Reassign Ticket"),
		__("Assign")
	);
}

function add_work_log(frm) {
	frappe.new_doc("Work Log", {
		ticket: frm.doc.name,
		engineer: frappe.session.user,
		start_time: frappe.datetime.now_datetime(),
	});
}

function suggest(frm) {
	frappe.call({
		method: "turacoz_service_desk.turacoz_it_service_desk.api.ticket.suggest_articles",
		args: { ticket: frm.doc.name },
		freeze: true,
		callback({ message }) {
			const articles = (message && message.data) || [];
			if (!articles.length) {
				frappe.msgprint(__("No matching knowledge articles found."));
				return;
			}
			const html = articles
				.map(
					(a) =>
						`<li><a href="/app/knowledge-article/${a.name}">${frappe.utils.escape_html(
							a.title
						)}</a> <span class="text-muted">(${a.article_type}, score ${a.score})</span></li>`
				)
				.join("");
			frappe.msgprint({
				title: __("Suggested Articles"),
				message: `<ul>${html}</ul>`,
				wide: true,
			});
		},
	});
}

function make_linked(frm, doctype) {
	const fieldmap = {
		Incident: {
			title: frm.doc.subject,
			incident_type: "Degradation",
			ticket: frm.doc.name,
			affected_service: frm.doc.configuration_item,
		},
		Problem: {
			title: frm.doc.subject,
			category: frm.doc.category,
			priority: frm.doc.priority,
			description: frm.doc.description,
		},
		"Change Request": {
			title: frm.doc.subject,
			category: frm.doc.category,
			priority: frm.doc.priority,
			ticket: frm.doc.name,
		},
	};
	frappe.new_doc(doctype, fieldmap[doctype]);
}
