"""Frappe app hooks for the Turacoz IT Service Desk (TSD)."""

app_name = "turacoz_service_desk"
app_title = "Turacoz IT Service Desk"
app_publisher = "Turacoz Healthcare Solutions"
app_description = "Enterprise ITSM and ticketing for ERPNext 15 (ITIL aligned)"
app_email = "it@turacoz.com"
app_license = "Proprietary"
app_icon = "octicon octicon-tools"
app_color = "#5e64ff"

# ERPNext supplies Employee, Department, Asset, Project, Cost Center and Supplier,
# all of which this module links to.
required_apps = ["frappe/erpnext"]

# ---------------------------------------------------------------------------
# installation
# ---------------------------------------------------------------------------

before_install = "turacoz_service_desk.turacoz_it_service_desk.setup.install.before_install"
after_install = "turacoz_service_desk.turacoz_it_service_desk.setup.install.after_install"
after_migrate = "turacoz_service_desk.turacoz_it_service_desk.setup.install.after_migrate"

# ---------------------------------------------------------------------------
# permissions
# ---------------------------------------------------------------------------

SERVICE_TICKET_CONTROLLER = (
	"turacoz_service_desk.turacoz_it_service_desk.doctype.service_ticket.service_ticket"
)

permission_query_conditions = {
	"Service Ticket": f"{SERVICE_TICKET_CONTROLLER}.get_permission_query_conditions",
}

has_permission = {
	"Service Ticket": f"{SERVICE_TICKET_CONTROLLER}.has_permission",
}

# ---------------------------------------------------------------------------
# document events - immutable audit trail (PRD module 20)
# ---------------------------------------------------------------------------

AUDIT = "turacoz_service_desk.turacoz_it_service_desk.engine.audit"

AUDITED_DOCTYPES = (
	"Service Ticket",
	"Incident",
	"Problem",
	"Change Request",
	"Privileged Access Request",
	"Knowledge Article",
	"Configuration Item",
	"Work Log",
	"Ticket Comment",
	"SLA Policy",
	"Approval Matrix",
	"Service Desk Team",
)

doc_events = {
	doctype: {
		"after_insert": f"{AUDIT}.on_insert",
		"on_update": f"{AUDIT}.on_update",
		"on_trash": f"{AUDIT}.on_trash",
	}
	for doctype in AUDITED_DOCTYPES
}

# ---------------------------------------------------------------------------
# scheduler
# ---------------------------------------------------------------------------

AUTOMATION = "turacoz_service_desk.turacoz_it_service_desk.engine.automation"

scheduler_events = {
	"cron": {
		# SLA breach detection and escalation sweep
		"*/15 * * * *": [f"{AUTOMATION}.every_fifteen_minutes"],
	},
	"hourly": [f"{AUTOMATION}.hourly"],
	"daily": [f"{AUTOMATION}.daily"],
}

# ---------------------------------------------------------------------------
# portal
# ---------------------------------------------------------------------------

standard_portal_menu_items = [
	{
		"title": "IT Service Desk",
		"route": "/support",
		"reference_doctype": "Service Ticket",
		"role": "Employee",
	},
]

website_route_rules = []

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
#
# Every entry MUST be filtered down to this app's own records. An unfiltered entry
# (e.g. plain "Custom Field") exports every such record on the site it was exported
# from - other apps' custom fields, workspaces, roles and workflows included - and
# `bench migrate` then writes that snapshot over the target site. On production that
# silently reverts other teams' customisations.
#
# This app owns no custom fields, property setters, client scripts, workflows or
# notifications. Its roles are created by `setup.install.before_install`, and its
# number cards, charts and reports are created by `setup.desk.run`. The workspace is
# the one desk artefact worth version controlling.

fixtures = [
	{
		"dt": "Workspace",
		"filters": [["module", "=", "Turacoz IT Service Desk"]],
	},
]
