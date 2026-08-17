"""Installation and bootstrap routines for the Turacoz IT Service Desk.

Everything here is idempotent so it can be re-run after every migrate:

    bench --site <site> execute turacoz_service_desk.turacoz_it_service_desk.setup.install.after_install
"""

import frappe

MODULE = "Turacoz IT Service Desk"
APP = "turacoz_service_desk"

# ---------------------------------------------------------------------------
# roles
# ---------------------------------------------------------------------------

ROLES = [
	("Service Desk Executive", "Triage, assign and monitor tickets."),
	("Service Desk Engineer", "Works on assigned tickets, logs effort, resolves."),
	("Service Desk Team Lead", "Owns a team, reassigns, escalates, reviews SLA."),
	("Department Head", "Approves requests raised by their department."),
	("IT Manager", "Full control over the service desk, reports and approvals."),
	("CISO", "Security incidents, privileged access and audit oversight."),
	("Auditor", "Read only access for internal and external audits."),
]


def create_roles():
	for role_name, description in ROLES:
		if frappe.db.exists("Role", role_name):
			continue
		frappe.get_doc({
			"doctype": "Role",
			"role_name": role_name,
			"desk_access": 1,
			"is_custom": 1,
			"description": description,
		}).insert(ignore_permissions=True)
		print(f"  role   {role_name}")


def create_module_def():
	if frappe.db.exists("Module Def", MODULE):
		return
	frappe.get_doc({
		"doctype": "Module Def",
		"module_name": MODULE,
		"app_name": APP,
		"custom": 0,
	}).insert(ignore_permissions=True)
	print(f"  module {MODULE}")


# ---------------------------------------------------------------------------
# master data
# ---------------------------------------------------------------------------

# (category, [sub categories])
CATEGORIES = [
	("Infrastructure", ["Server", "Storage", "Backup", "Printer", "Hardware"]),
	("ERP", ["ERPNext Access", "ERP Report", "ERP Bug", "ERP Enhancement"]),
	("Website", ["Content Update", "Downtime", "SSL", "DNS"]),
	("Development", ["Custom Application", "API Integration", "Bug Fix"]),
	("Cloud", ["Azure", "AWS", "Cloud VM", "Cloud Storage"]),
	("Database", ["Backup Restore", "Performance", "Access"]),
	("Security", ["Phishing", "Malware", "Vulnerability", "Privileged Access"]),
	("Networking", ["Firewall", "VPN", "Internet", "Switch / Router"]),
	("Office365", ["Email", "SharePoint", "OneDrive", "Teams", "License"]),
	("HRMS", ["Attendance", "Payroll", "Leave"]),
	("Finance", ["Invoicing", "Payments", "Reports"]),
	("CRM", ["Leads", "Opportunities", "Reports"]),
	("Software", ["Installation", "License", "Upgrade"]),
	("Others", []),
]

DEFAULT_SLA = "Standard IT SLA"

# priority -> (response seconds, resolution seconds)
SLA_TARGETS = {
	"Critical": (30 * 60, 4 * 3600),
	"High": (60 * 60, 8 * 3600),
	"Medium": (4 * 3600, 24 * 3600),
	"Low": (8 * 3600, 72 * 3600),
}

WORKING_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

DEFAULT_TEAM = "IT Service Desk"

# (service, category, sub category, priority, approval required)
CATALOG = [
	("New Employee Account", "Office365", "License", "High", 1),
	("Password Reset", "Office365", "Email", "High", 0),
	("Office365 License", "Office365", "License", "Medium", 1),
	("VPN Access", "Networking", "VPN", "Medium", 1),
	("New Laptop", "Infrastructure", "Hardware", "Medium", 1),
	("Software Installation", "Software", "Installation", "Low", 0),
	("Firewall Rule Change", "Networking", "Firewall", "High", 1),
	("DNS Update", "Website", "DNS", "Medium", 1),
	("SSL Installation", "Website", "SSL", "High", 1),
	("Website Update", "Website", "Content Update", "Low", 0),
	("ERP Report Request", "ERP", "ERP Report", "Low", 0),
	("Custom Development", "Development", "Custom Application", "Medium", 1),
	("API Integration", "Development", "API Integration", "Medium", 1),
	("Database Restore", "Database", "Backup Restore", "Critical", 1),
	("Cloud Server Provisioning", "Cloud", "Cloud VM", "High", 1),
	("Backup Restore", "Infrastructure", "Backup", "High", 1),
]

APPROVAL_MATRICES = [
	{
		"matrix_name": "Standard Service Request Approval",
		"applies_to": "Service Ticket",
		"approval_mode": "Sequential",
		"levels": [
			{"level": 1, "approver_type": "Requester Manager", "is_mandatory": 1},
			{"level": 2, "approver_type": "IT Manager", "is_mandatory": 1},
		],
	},
	{
		"matrix_name": "Standard Change Approval",
		"applies_to": "Change Request",
		"approval_mode": "Sequential",
		"levels": [
			{"level": 1, "approver_type": "Team Lead", "is_mandatory": 1},
			{"level": 2, "approver_type": "IT Manager", "is_mandatory": 1},
			{
				"level": 3,
				"approver_type": "CISO",
				"is_mandatory": 0,
				"condition": "doc.risk in ('High', 'Critical')",
			},
		],
	},
	{
		"matrix_name": "Privileged Access Approval",
		"applies_to": "Privileged Access Request",
		"approval_mode": "Sequential",
		"levels": [
			{"level": 1, "approver_type": "Requester Manager", "is_mandatory": 1},
			{"level": 2, "approver_type": "IT Manager", "is_mandatory": 1},
			{"level": 3, "approver_type": "CISO", "is_mandatory": 1},
		],
	},
]


def create_categories():
	for parent, children in CATEGORIES:
		if not frappe.db.exists("IT Service Category", parent):
			frappe.get_doc({
				"doctype": "IT Service Category",
				"category_name": parent,
				"is_group": 1 if children else 0,
				"is_active": 1,
				"default_priority": "Medium",
			}).insert(ignore_permissions=True)
		for child in children:
			if frappe.db.exists("IT Service Category", child):
				continue
			frappe.get_doc({
				"doctype": "IT Service Category",
				"category_name": child,
				"parent_service_category": parent,
				"is_group": 0,
				"is_active": 1,
				"default_priority": "Medium",
			}).insert(ignore_permissions=True)
	print(f"  categories ready ({frappe.db.count('IT Service Category')})")


def create_sla_policy():
	if frappe.db.exists("SLA Policy", DEFAULT_SLA):
		return frappe.get_doc("SLA Policy", DEFAULT_SLA)

	doc = frappe.get_doc({
		"doctype": "SLA Policy",
		"policy_name": DEFAULT_SLA,
		"is_default": 1,
		"is_active": 1,
		"apply_24x7": 0,
		"description": "Default response and resolution targets for all IT tickets.",
		"priority_rules": [
			{"priority": p, "response_time": r, "resolution_time": res}
			for p, (r, res) in SLA_TARGETS.items()
		],
		"working_days": [
			{"workday": d, "start_time": "09:00:00", "end_time": "18:00:00"}
			for d in WORKING_DAYS
		],
		"pause_statuses": [
			{"status": "Pending User", "description": "Waiting for information from the requester."},
			{"status": "Pending Vendor", "description": "Waiting for a third party or vendor."},
		],
		"escalation_rules": [
			{
				"escalation_type": "Response",
				"after_percent": 75,
				"escalate_to_role": "Service Desk Team Lead",
				"notify_requester": 0,
			},
			{
				"escalation_type": "Resolution",
				"after_percent": 75,
				"escalate_to_role": "Service Desk Team Lead",
				"notify_requester": 0,
			},
			{
				"escalation_type": "Resolution",
				"after_percent": 100,
				"escalate_to_role": "IT Manager",
				"increase_priority": 1,
				"notify_requester": 1,
			},
		],
	})
	doc.insert(ignore_permissions=True)
	print(f"  sla    {DEFAULT_SLA}")
	return doc


def create_team():
	if frappe.db.exists("Service Desk Team", DEFAULT_TEAM):
		return frappe.get_doc("Service Desk Team", DEFAULT_TEAM)

	lead = frappe.db.get_value("User", {"name": "Administrator"}, "name") or "Administrator"
	doc = frappe.get_doc({
		"doctype": "Service Desk Team",
		"team_name": DEFAULT_TEAM,
		"team_lead": lead,
		"assignment_method": "Load Balancing",
		"is_active": 1,
		"description": "Catch-all team for tickets without a category specific team.",
		"members": [{"user": lead, "role_in_team": "Lead", "max_open_tickets": 0, "is_available": 1}],
	})
	doc.insert(ignore_permissions=True)
	print(f"  team   {DEFAULT_TEAM}")
	return doc


def create_approval_matrices():
	for spec in APPROVAL_MATRICES:
		if frappe.db.exists("Approval Matrix", spec["matrix_name"]):
			continue
		doc = frappe.get_doc({"doctype": "Approval Matrix", "is_active": 1, **spec})
		doc.insert(ignore_permissions=True)
		print(f"  matrix {spec['matrix_name']}")


def create_catalog():
	default_sla = DEFAULT_SLA if frappe.db.exists("SLA Policy", DEFAULT_SLA) else None
	matrix = ("Standard Service Request Approval"
	          if frappe.db.exists("Approval Matrix", "Standard Service Request Approval") else None)

	for service, category, sub_category, priority, approval in CATALOG:
		if frappe.db.exists("Service Catalog", service):
			continue
		if not frappe.db.exists("IT Service Category", category):
			continue
		frappe.get_doc({
			"doctype": "Service Catalog",
			"service_name": service,
			"category": category,
			"sub_category": sub_category if frappe.db.exists("IT Service Category", sub_category) else None,
			"is_active": 1,
			"default_priority": priority,
			"sla_policy": default_sla,
			"approval_required": approval,
			"approval_matrix": matrix if approval else None,
		}).insert(ignore_permissions=True)
	print(f"  catalog ready ({frappe.db.count('Service Catalog')})")


def configure_settings():
	settings = frappe.get_single("Service Desk Settings")
	if not settings.default_sla_policy and frappe.db.exists("SLA Policy", DEFAULT_SLA):
		settings.default_sla_policy = DEFAULT_SLA
	if not settings.default_team and frappe.db.exists("Service Desk Team", DEFAULT_TEAM):
		settings.default_team = DEFAULT_TEAM
	settings.save(ignore_permissions=True)
	print("  settings configured")


# ---------------------------------------------------------------------------
# entry points
# ---------------------------------------------------------------------------

def before_install():
	"""Roles must exist before the DocType JSON files are imported.

	The Module Def is deliberately left to Frappe's own `add_module_defs`, which runs
	right after this hook and raises on a duplicate.
	"""
	create_roles()
	frappe.db.commit()


def after_install():
	create_module_def()
	create_roles()

	if not frappe.db.exists("DocType", "IT Service Category"):
		print("DocTypes are not installed yet. Run `bench --site <site> migrate` first.")
		return

	create_categories()
	create_sla_policy()
	create_team()
	create_approval_matrices()
	create_catalog()
	configure_settings()
	frappe.db.commit()

	# reports, number cards, charts and the workspace
	try:
		from turacoz_service_desk.turacoz_it_service_desk.setup import desk

		desk.run()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Service desk: desk artefacts failed")
		print("  desk artefacts failed, run setup.desk.run manually (see the error log)")

	print("Turacoz IT Service Desk: setup complete.")


def after_migrate():
	"""Keep roles present after every migrate without re-seeding master data."""
	create_module_def()
	create_roles()
	frappe.db.commit()
