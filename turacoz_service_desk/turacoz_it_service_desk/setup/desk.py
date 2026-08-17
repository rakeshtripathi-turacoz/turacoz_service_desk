"""Desk artefacts: script reports, number cards, charts and the workspace.

    bench --site <site> execute turacoz_service_desk.turacoz_it_service_desk.setup.desk.run
"""

import json

import frappe

MODULE = "Turacoz IT Service Desk"

READ_ROLES = ["System Manager", "IT Manager", "Service Desk Team Lead",
              "Service Desk Executive", "Auditor"]
ENGINEER_ROLES = READ_ROLES + ["Service Desk Engineer"]

# report name -> (ref doctype, roles)
REPORTS = {
	"Service Desk Ticket Summary": ("Service Ticket", ENGINEER_ROLES),
	"SLA Compliance": ("Service Ticket", READ_ROLES),
	"SLA Violations": ("Service Ticket", READ_ROLES),
	"Engineer Performance": ("Service Ticket", READ_ROLES),
	"Ticket Aging": ("Service Ticket", ENGINEER_ROLES),
	"Ticket Analysis": ("Service Ticket", READ_ROLES),
	"Reopened Tickets": ("Service Ticket", READ_ROLES),
	"Monthly KPI": ("Service Ticket", READ_ROLES),
	"Change Success Report": ("Change Request", READ_ROLES),
	"Incident Report": ("Incident", READ_ROLES + ["CISO"]),
	"Knowledge Base Usage": ("Knowledge Article", ENGINEER_ROLES),
	"Top Requesters": ("Service Ticket", READ_ROLES),
}

OPEN_FILTER = ["status", "not in", ["Resolved", "Closed", "Cancelled"]]


def desk_filters(document_type, conditions):
	"""Number Cards and Dashboard Charts store filters the way the desk filter area reads
	them: [doctype, fieldname, operator, value, hidden].

	A bare [fieldname, operator, value] still works server side, but the client treats
	index 1 as the fieldname and reports "Invalid filter: not in".
	"""
	return [
		[document_type, fieldname, operator, value, False]
		for fieldname, operator, value in conditions
	]

NUMBER_CARDS = [
	{"label": "Open Tickets", "document_type": "Service Ticket", "color": "#5e64ff",
	 "filters_json": [OPEN_FILTER]},
	{"label": "Critical Open Tickets", "document_type": "Service Ticket", "color": "#e24c4c",
	 "filters_json": [OPEN_FILTER, ["priority", "=", "Critical"]]},
	{"label": "SLA Breached", "document_type": "Service Ticket", "color": "#ff5858",
	 "filters_json": [["sla_status", "in",
	                   ["Failed", "Response Overdue", "Resolution Overdue"]]]},
	{"label": "Unassigned Tickets", "document_type": "Service Ticket", "color": "#ffa00a",
	 "filters_json": [OPEN_FILTER, ["assigned_engineer", "is", "not set"]]},
	{"label": "Escalated Tickets", "document_type": "Service Ticket", "color": "#cb2929",
	 "filters_json": [OPEN_FILTER, ["is_escalated", "=", 1]]},
	{"label": "Open Incidents", "document_type": "Incident", "color": "#ff8c00",
	 "filters_json": [["status", "not in", ["Resolved", "Closed"]]]},
	{"label": "Changes Awaiting Approval", "document_type": "Change Request", "color": "#7575ff",
	 "filters_json": [["approval_status", "=", "Pending"]]},
	{"label": "Active Privileged Access", "document_type": "Privileged Access Request",
	 "color": "#29cd42", "filters_json": [["status", "in", ["Approved", "Active"]]]},
]

CHARTS = [
	{"chart_name": "Tickets by Priority", "document_type": "Service Ticket", "type": "Donut",
	 "chart_type": "Group By", "group_by_type": "Count", "group_by_based_on": "priority",
	 "filters_json": [OPEN_FILTER]},
	{"chart_name": "Tickets by Status", "document_type": "Service Ticket", "type": "Bar",
	 "chart_type": "Group By", "group_by_type": "Count", "group_by_based_on": "status",
	 "filters_json": [OPEN_FILTER]},
	{"chart_name": "Tickets by Category", "document_type": "Service Ticket", "type": "Bar",
	 "chart_type": "Group By", "group_by_type": "Count", "group_by_based_on": "category",
	 "number_of_groups": 10, "filters_json": []},
	{"chart_name": "Ticket Volume Trend", "document_type": "Service Ticket", "type": "Line",
	 "chart_type": "Count", "based_on": "creation", "timespan": "Last Quarter",
	 "time_interval": "Weekly", "timeseries": 1, "filters_json": []},
	{"chart_name": "Incidents by Severity", "document_type": "Incident", "type": "Bar",
	 "chart_type": "Group By", "group_by_type": "Count", "group_by_based_on": "severity",
	 "filters_json": []},
]

WORKSPACE = "IT Service Desk"

LINK_CARDS = [
	("Tickets", [("Service Ticket", "DocType"), ("Work Log", "DocType"),
	             ("Ticket Comment", "DocType"), ("Ticket Feedback", "DocType")]),
	("Incidents, Problems & Changes", [("Incident", "DocType"), ("Problem", "DocType"),
	                                   ("Change Request", "DocType")]),
	("Access & Audit", [("Privileged Access Request", "DocType"),
	                    ("Service Desk Audit Log", "DocType")]),
	("Knowledge & CMDB", [("Knowledge Article", "DocType"),
	                      ("Configuration Item", "DocType")]),
	("Configuration", [("Service Desk Settings", "DocType"), ("Service Desk Team", "DocType"),
	                   ("SLA Policy", "DocType"), ("Approval Matrix", "DocType"),
	                   ("IT Service Category", "DocType"), ("Service Catalog", "DocType"),
	                   ("Engineer Skill", "DocType")]),
	("Reports", [(name, "Report") for name in REPORTS]),
]

SHORTCUTS = [
	{"label": "Service Ticket", "type": "DocType", "link_to": "Service Ticket", "color": "Blue",
	 "stats_filter": {"status": ["not in", ["Resolved", "Closed", "Cancelled"]]}},
	# stats_filter is evaluated as javascript by the desk, so it can reference the session
	{"label": "My Open Tickets", "type": "DocType", "link_to": "Service Ticket", "color": "Orange",
	 "stats_filter_js": '{"assigned_engineer": ["=", frappe.session.user], '
	                    '"status": ["not in", ["Resolved", "Closed", "Cancelled"]]}'},
	{"label": "Incident", "type": "DocType", "link_to": "Incident", "color": "Red"},
	{"label": "Change Request", "type": "DocType", "link_to": "Change Request", "color": "Purple"},
	{"label": "Knowledge Article", "type": "DocType", "link_to": "Knowledge Article",
	 "color": "Green"},
	{"label": "SLA Compliance", "type": "Report", "link_to": "SLA Compliance", "color": "Cyan"},
	{"label": "Service Desk Settings", "type": "DocType", "link_to": "Service Desk Settings",
	 "color": "Grey"},
]


# ---------------------------------------------------------------------------
# reports
# ---------------------------------------------------------------------------

def create_reports():
	for name, (ref_doctype, roles) in REPORTS.items():
		if frappe.db.exists("Report", name):
			doc = frappe.get_doc("Report", name)
			doc.ref_doctype = ref_doctype
			doc.module = MODULE
			doc.report_type = "Script Report"
			doc.is_standard = "Yes"
			doc.disabled = 0
			_set_roles(doc, roles)
			doc.save(ignore_permissions=True)
			continue

		doc = frappe.get_doc({
			"doctype": "Report",
			"report_name": name,
			"ref_doctype": ref_doctype,
			"report_type": "Script Report",
			"module": MODULE,
			"is_standard": "Yes",
			"roles": [{"role": role} for role in roles],
		})
		doc.insert(ignore_permissions=True)
		print(f"  report {name}")


def _set_roles(doc, roles):
	existing = {row.role for row in doc.roles}
	for role in roles:
		if role not in existing:
			doc.append("roles", {"role": role})


# ---------------------------------------------------------------------------
# number cards and charts
# ---------------------------------------------------------------------------

def create_number_cards():
	for spec in NUMBER_CARDS:
		filters = json.dumps(desk_filters(spec["document_type"], spec["filters_json"]))

		if frappe.db.exists("Number Card", spec["label"]):
			# repair filters written by an earlier version in the short form
			if frappe.db.get_value("Number Card", spec["label"], "filters_json") != filters:
				frappe.db.set_value("Number Card", spec["label"], "filters_json", filters)
				print(f"  card   {spec['label']} (filters repaired)")
			continue

		frappe.get_doc({
			"doctype": "Number Card",
			"name": spec["label"],
			"label": spec["label"],
			"type": "Document Type",
			"document_type": spec["document_type"],
			"function": "Count",
			"is_public": 1,
			"is_standard": 0,
			"module": MODULE,
			"color": spec.get("color"),
			"show_percentage_stats": 1,
			"stats_time_interval": "Weekly",
			"filters_json": filters,
		}).insert(ignore_permissions=True)
		print(f"  card   {spec['label']}")


def create_charts():
	for spec in CHARTS:
		filters = json.dumps(desk_filters(spec["document_type"], spec.get("filters_json", [])))

		if frappe.db.exists("Dashboard Chart", spec["chart_name"]):
			if frappe.db.get_value("Dashboard Chart", spec["chart_name"], "filters_json") != filters:
				frappe.db.set_value("Dashboard Chart", spec["chart_name"], "filters_json", filters)
				print(f"  chart  {spec['chart_name']} (filters repaired)")
			continue

		payload = {
			"doctype": "Dashboard Chart",
			"name": spec["chart_name"],
			"chart_name": spec["chart_name"],
			"chart_type": spec["chart_type"],
			"document_type": spec["document_type"],
			"type": spec["type"],
			"is_public": 1,
			"is_standard": 0,
			"module": MODULE,
			"filters_json": filters,
		}
		for key in ("group_by_type", "group_by_based_on", "based_on", "timespan",
		            "time_interval", "timeseries", "number_of_groups"):
			if key in spec:
				payload[key] = spec[key]
		frappe.get_doc(payload).insert(ignore_permissions=True)
		print(f"  chart  {spec['chart_name']}")


# ---------------------------------------------------------------------------
# workspace
# ---------------------------------------------------------------------------

def build_content():
	blocks = [
		{"id": "sd_header", "type": "header",
		 "data": {"text": "<span class=\"h4\">IT Service Desk</span>", "col": 12}},
	]
	for spec in SHORTCUTS:
		blocks.append({"id": f"sc_{_slug(spec['label'])}", "type": "shortcut",
		               "data": {"shortcut_name": spec["label"], "col": 3}})

	blocks.append({"id": "sd_kpi", "type": "header",
	               "data": {"text": "<span class=\"h4\">Key Numbers</span>", "col": 12}})
	for card in NUMBER_CARDS:
		blocks.append({"id": f"nc_{_slug(card['label'])}", "type": "number_card",
		               "data": {"number_card_name": card["label"], "col": 3}})

	blocks.append({"id": "sd_charts", "type": "header",
	               "data": {"text": "<span class=\"h4\">Analytics</span>", "col": 12}})
	for chart in CHARTS[:4]:
		blocks.append({"id": f"ch_{_slug(chart['chart_name'])}", "type": "chart",
		               "data": {"chart_name": chart["chart_name"], "col": 6}})

	blocks.append({"id": "sd_links", "type": "header",
	               "data": {"text": "<span class=\"h4\">Masters & Reports</span>", "col": 12}})
	for label, _links in LINK_CARDS:
		blocks.append({"id": f"cd_{_slug(label)}", "type": "card",
		               "data": {"card_name": label, "col": 4}})
	return json.dumps(blocks)


def build_links():
	rows = []
	for label, links in LINK_CARDS:
		rows.append({"type": "Card Break", "label": label, "link_count": len(links),
		             "hidden": 0, "onboard": 0})
		for link_to, link_type in links:
			row = {
				"type": "Link", "label": link_to, "link_type": link_type,
				"link_to": link_to, "hidden": 0, "onboard": 0, "link_count": 0,
			}
			if link_type == "Report":
				row["is_query_report"] = 1
				row["dependencies"] = REPORTS[link_to][0]
			rows.append(row)
	return rows


def create_workspace():
	exists = frappe.db.exists("Workspace", WORKSPACE)
	if exists:
		doc = frappe.get_doc("Workspace", WORKSPACE)
		doc.links = []
		doc.shortcuts = []
		doc.number_cards = []
		doc.charts = []
	else:
		doc = frappe.new_doc("Workspace")
		doc.name = WORKSPACE

	doc.title = WORKSPACE
	doc.label = WORKSPACE
	doc.module = MODULE
	doc.icon = "tool"
	doc.indicator_color = "blue"
	doc.public = 1
	doc.is_hidden = 0
	doc.sequence_id = 40.0
	doc.content = build_content()

	for spec in SHORTCUTS:
		row = {"type": spec["type"], "link_to": spec["link_to"], "label": spec["label"],
		       "color": spec.get("color")}
		if spec.get("stats_filter_js"):
			row["stats_filter"] = spec["stats_filter_js"]
		elif spec.get("stats_filter"):
			row["stats_filter"] = json.dumps(spec["stats_filter"])
		doc.append("shortcuts", row)

	for row in build_links():
		doc.append("links", row)

	for card in NUMBER_CARDS:
		doc.append("number_cards", {"number_card_name": card["label"], "label": card["label"]})

	for chart in CHARTS:
		doc.append("charts", {"chart_name": chart["chart_name"], "label": chart["chart_name"]})

	doc.flags.ignore_links = True
	if exists:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)
	print(f"  workspace {WORKSPACE}")


def _slug(value):
	return value.lower().replace(" ", "_").replace("&", "and").replace(",", "")


def run():
	print("== reports ==")
	create_reports()
	print("== number cards ==")
	create_number_cards()
	print("== charts ==")
	create_charts()
	print("== workspace ==")
	create_workspace()
	frappe.db.commit()
	print("Desk artefacts ready.")
