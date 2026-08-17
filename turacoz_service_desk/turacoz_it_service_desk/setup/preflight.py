"""Pre-installation safety check for an existing ERPNext 15 site.

Run this BEFORE `bench install-app turacoz_service_desk`:

    bench --site erp.turacoz.com execute \\
        turacoz_service_desk.turacoz_it_service_desk.setup.preflight.check

It never writes anything. It reports:
  * DocType name clashes with apps already installed on the site
  * Role name clashes
  * missing dependencies (ERPNext doctypes this module links to)
  * scheduler / email configuration that the SLA and notification engines need
"""

import frappe

MODULE = "Turacoz IT Service Desk"

OWN_DOCTYPES = [
	"Service Ticket", "Incident", "Problem", "Change Request", "Privileged Access Request",
	"Work Log", "Ticket Comment", "Ticket Feedback", "IT Service Category", "Service Catalog",
	"SLA Policy", "Approval Matrix", "Service Desk Team", "Engineer Skill",
	"Configuration Item", "Knowledge Article", "Service Desk Settings",
	"Service Desk Audit Log", "Service Desk Team Member", "Service Catalog Document",
	"SLA Priority Rule", "SLA Working Day", "SLA Escalation Rule", "SLA Pause Status",
	"SLA Event", "Ticket Timeline", "Ticket Watcher", "Ticket Asset Link", "Approval History",
	"Approval Matrix Level", "Assignment History", "Related Record", "Notification Sent",
	"Privileged Access Scope", "Change Affected Service", "CI Relationship",
]

OWN_ROLES = [
	"Service Desk Executive", "Service Desk Engineer", "Service Desk Team Lead",
	"Department Head", "IT Manager", "CISO", "Auditor",
]

REQUIRED_DOCTYPES = [
	"User", "Role", "Employee", "Department", "Asset", "Project", "Cost Center",
	"Supplier", "Holiday List", "ToDo", "Notification Log", "File",
]

REPORT_NAMES = [
	"Service Desk Ticket Summary", "SLA Compliance", "SLA Violations",
	"Engineer Performance", "Ticket Aging", "Ticket Analysis", "Reopened Tickets",
	"Monthly KPI", "Change Success Report", "Incident Report", "Knowledge Base Usage",
	"Top Requesters",
]


def check():
	print(f"\nPreflight for site: {frappe.local.site}")
	print("=" * 72)

	blockers, warnings = [], []

	print("\n1. Installed apps")
	apps = frappe.get_installed_apps()
	print("   " + ", ".join(apps))
	if "erpnext" not in apps:
		blockers.append("ERPNext is not installed - this module links to Employee, Asset, "
		                "Department, Project, Cost Center and Supplier.")
	if "turacoz_service_desk" in apps:
		warnings.append("turacoz_service_desk is already installed - this will be an upgrade, "
		                "not a fresh install.")

	print("\n2. DocType name clashes")
	clashes = []
	for doctype in OWN_DOCTYPES:
		module = frappe.db.get_value("DocType", doctype, "module")
		if module and module != MODULE:
			clashes.append((doctype, module))
	if clashes:
		for doctype, module in clashes:
			print(f"   CLASH  {doctype:32} already owned by module '{module}'")
			blockers.append(f"DocType '{doctype}' already exists in module '{module}'.")
	else:
		print("   none")

	print("\n3. Report name clashes")
	report_clashes = [
		(name, frappe.db.get_value("Report", name, "module"))
		for name in REPORT_NAMES
		if frappe.db.exists("Report", name)
		and frappe.db.get_value("Report", name, "module") != MODULE
	]
	for name, module in report_clashes:
		print(f"   CLASH  {name:32} already owned by module '{module}'")
		blockers.append(f"Report '{name}' already exists in module '{module}'.")
	if not report_clashes:
		print("   none")

	print("\n4. Roles that already exist (they will be reused, not overwritten)")
	existing_roles = [role for role in OWN_ROLES if frappe.db.exists("Role", role)]
	print("   " + (", ".join(existing_roles) if existing_roles else "none"))

	print("\n5. Required dependencies")
	missing = [doctype for doctype in REQUIRED_DOCTYPES if not frappe.db.exists("DocType", doctype)]
	if missing:
		print("   MISSING " + ", ".join(missing))
		blockers.append("Missing dependency doctypes: " + ", ".join(missing))
	else:
		print("   all present")

	print("\n6. Workspace name")
	workspace_module = frappe.db.get_value("Workspace", "IT Service Desk", "module")
	if workspace_module and workspace_module != MODULE:
		print(f"   CLASH  Workspace 'IT Service Desk' owned by '{workspace_module}'")
		blockers.append("Workspace 'IT Service Desk' already exists.")
	else:
		print("   free")

	print("\n7. Runtime configuration")
	if frappe.utils.cint(frappe.local.conf.get("pause_scheduler")):
		warnings.append("The scheduler is paused in site config - SLA escalation, auto close "
		                "and access expiry will not run.")
	if not frappe.db.get_value("Email Account", {"enable_outgoing": 1}, "name"):
		warnings.append("No outgoing Email Account is enabled - email notifications will be "
		                "logged as failed. In-app notifications still work.")
	if not frappe.db.count("Holiday List"):
		warnings.append("No Holiday List exists - SLA working time will not exclude holidays "
		                "until one is created and set on the SLA Policy.")
	print("   checked scheduler, outgoing email and holiday list")

	print("\n" + "=" * 72)
	if blockers:
		print(f"BLOCKERS ({len(blockers)}) - resolve these before installing:")
		for item in blockers:
			print("  x " + item)
	else:
		print("No blockers. The app can be installed on this site.")

	if warnings:
		print(f"\nWarnings ({len(warnings)}):")
		for item in warnings:
			print("  ! " + item)

	print()
	return {"blockers": blockers, "warnings": warnings}
