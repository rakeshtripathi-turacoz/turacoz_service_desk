"""Demo data for UAT and report validation.

    bench --site <site> execute turacoz_service_desk.turacoz_it_service_desk.setup.demo.seed
    bench --site <site> execute turacoz_service_desk.turacoz_it_service_desk.setup.demo.purge

Every record created here is tagged `demo` (tickets) or prefixed `[DEMO]`
(incidents, problems, changes, articles) so purge can remove them cleanly.
"""

import random

import frappe
from frappe.utils import add_days, add_to_date, get_datetime, now_datetime

DEMO_TAG = "demo"
DEMO_PREFIX = "[DEMO]"

SUBJECTS = [
	("Outlook keeps disconnecting", "Office365", "Email", "Incident"),
	("Cannot access the shared drive", "Office365", "OneDrive", "Incident"),
	("VPN drops every few minutes", "Networking", "VPN", "Incident"),
	("Request a new laptop", "Infrastructure", "Hardware", "Service Request"),
	("Password reset for the finance portal", "Office365", "Email", "Service Request"),
	("ERP invoice report is wrong", "ERP", "ERP Report", "Incident"),
	("Add a firewall rule for the new vendor", "Networking", "Firewall", "Service Request"),
	("Website is returning 502", "Website", "Downtime", "Incident"),
	("SSL certificate expired", "Website", "SSL", "Incident"),
	("Install Adobe Acrobat", "Software", "Installation", "Service Request"),
	("Database restore for the UAT server", "Database", "Backup Restore", "Service Request"),
	("Printer on the second floor is offline", "Infrastructure", "Printer", "Incident"),
	("Suspicious phishing email received", "Security", "Phishing", "Incident"),
	("New starter account setup", "Office365", "License", "Service Request"),
	("Slow ERP performance in the morning", "ERP", "ERP Bug", "Incident"),
	("Grant SharePoint access to the audit team", "Office365", "SharePoint", "Service Request"),
]

RESOLUTIONS = [
	"Recreated the user profile and reconnected the service.",
	"Applied the vendor patch and restarted the service.",
	"Corrected the permission set and confirmed access with the user.",
	"Replaced the faulty hardware and validated with the requester.",
	"Rolled back the recent configuration change.",
]

STATUS_MIX = (
	["Closed"] * 9 + ["Resolved"] * 3 + ["In Progress"] * 3 + ["Assigned"] * 2 +
	["Open"] * 2 + ["Pending User"]
)


def _engineers(limit=5):
	users = frappe.get_all(
		"User",
		filters={"enabled": 1, "user_type": "System User",
		         "name": ["not in", ("Administrator", "Guest")]},
		pluck="name",
		limit=limit,
	)
	return users or ["Administrator"]


def seed(count=60):
	"""Create `count` demo tickets spread over the last 90 days, plus ITIL records."""
	count = int(count)
	random.seed(42)
	engineers = _engineers()
	requesters = _engineers(12)
	now = now_datetime()

	print(f"seeding {count} demo tickets using {len(engineers)} engineers")
	created = []
	for index in range(count):
		subject, category, sub_category, ticket_type = random.choice(SUBJECTS)
		priority = random.choice(["Low", "Medium", "Medium", "High", "High", "Critical"])
		status = random.choice(STATUS_MIX)
		age_days = random.randint(0, 90)
		opened = add_to_date(now, days=-age_days, hours=-random.randint(0, 8))

		doc = frappe.get_doc({
			"doctype": "Service Ticket",
			"subject": f"{subject} ({index + 1})",
			"description": f"<p>{subject}. Reported through the demo data seeder.</p>",
			"ticket_type": ticket_type,
			"category": category,
			"sub_category": sub_category,
			"priority": priority,
			"impact": random.choice(["Low", "Medium", "High"]),
			"urgency": random.choice(["Low", "Medium", "High"]),
			"source": random.choice(["Portal", "Email", "Phone", "Chat"]),
			"requester": random.choice(requesters),
			"assigned_engineer": random.choice(engineers),
			"opened_on": opened,
			"tags": DEMO_TAG,
			"status": "Open",
		})
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)

		_walk_to_status(doc, status, opened, now)
		created.append(doc.name)

		# backdate the audit columns so the trend reports look real
		frappe.db.set_value("Service Ticket", doc.name, "creation", opened,
		                    update_modified=False)

	frappe.db.commit()
	print(f"  {len(created)} tickets")

	_seed_feedback(created)
	_seed_itil(created, engineers)
	frappe.db.commit()
	print("demo data ready")
	return created


def _walk_to_status(doc, target, opened, now):
	"""Move a ticket along a realistic path so SLA and timeline data is populated."""
	path = {
		"Open": [],
		"Assigned": ["Assigned"],
		"In Progress": ["Assigned", "In Progress"],
		"Pending User": ["Assigned", "In Progress", "Pending User"],
		"Resolved": ["Assigned", "In Progress", "Resolved"],
		"Closed": ["Assigned", "In Progress", "Resolved", "Closed"],
	}[target]

	for status in path:
		if status == "Resolved":
			doc.resolution = random.choice(RESOLUTIONS)
			doc.resolution_category = random.choice(
				["Fixed", "Workaround Provided", "Configuration Change", "User Education"]
			)
		doc.status = status
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)

	if target in ("Resolved", "Closed"):
		# the ticket was inserted with a backdated opened_on, so its deadlines are already
		# in the past; recompute the outcome from the simulated timings instead
		responded = add_to_date(opened, minutes=random.randint(5, 240))
		resolved = add_to_date(opened, hours=random.randint(1, 60))
		if resolved > now:
			resolved = now
		closed = add_to_date(resolved, hours=random.randint(1, 24))

		response_met = int(bool(doc.response_by) and responded <= get_datetime(doc.response_by))
		resolution_met = int(bool(doc.resolution_by) and resolved <= get_datetime(doc.resolution_by))

		updates = {
			"resolved_on": resolved,
			"closed_on": closed if target == "Closed" else None,
			"first_responded_on": responded,
			"response_sla_met": response_met,
			"resolution_sla_met": resolution_met,
			"sla_status": "Fulfilled" if (response_met and resolution_met) else "Failed",
		}
		if random.random() < 0.15:
			updates["reopen_count"] = 1
			updates["reopened_on"] = add_to_date(resolved, hours=2)
		frappe.db.set_value("Service Ticket", doc.name, updates, update_modified=False)

	if random.random() < 0.15:
		frappe.db.set_value("Service Ticket", doc.name,
		                    {"is_escalated": 1, "escalation_level": 1}, update_modified=False)


def _seed_feedback(tickets):
	closed = frappe.get_all(
		"Service Ticket", filters={"name": ["in", tickets], "status": "Closed"}, pluck="name"
	)
	for name in closed:
		if random.random() > 0.6:
			continue
		rating = random.choice([0.6, 0.8, 0.8, 1.0, 1.0, 0.4])
		frappe.get_doc({
			"doctype": "Ticket Feedback",
			"ticket": name,
			"rating": rating,
			"response_speed": rating,
			"resolution_quality": rating,
			"comments": "Demo feedback.",
		}).insert(ignore_permissions=True)


def _seed_itil(tickets, engineers):
	now = now_datetime()

	for severity, incident_type, title in (
		("S1 - Critical", "Outage", "Mail relay outage"),
		("S2 - High", "Degradation", "ERP slowness during payroll run"),
		("S2 - High", "Phishing", "Targeted phishing campaign"),
		("S3 - Medium", "Hardware Failure", "Failed disk in the backup array"),
	):
		doc = frappe.get_doc({
			"doctype": "Incident",
			"title": f"{DEMO_PREFIX} {title}",
			"incident_type": incident_type,
			"severity": severity,
			"status": "Resolved",
			"affected_users": random.randint(5, 200),
			"business_impact": "Demo incident created by the seeder.",
			"incident_manager": random.choice(engineers),
			"detection_time": add_days(now, -random.randint(5, 60)),
			"containment_actions": "Isolated the affected service.",
			"resolution": "Service restored and validated.",
			"root_cause": "Demo root cause.",
			"lessons_learned": "Add monitoring for early detection.",
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Incident", doc.name,
		                    {"containment_time": add_to_date(doc.detection_time, hours=2),
		                     "resolution_time": add_to_date(doc.detection_time, hours=6)},
		                    update_modified=False)

	frappe.get_doc({
		"doctype": "Problem",
		"title": f"{DEMO_PREFIX} Recurring Outlook disconnects",
		"status": "Known Error",
		"priority": "High",
		"category": "Office365",
		"description": "Multiple incidents point at the same mailbox proxy.",
		"workaround": "Restart the Outlook profile.",
		"root_cause": "Proxy connection pool exhaustion.",
		"is_known_error": 1,
	}).insert(ignore_permissions=True)

	for change_type, risk, result, title in (
		("Normal", "Medium", "Successful", "Upgrade the mail relay"),
		("Normal", "Low", "Successful", "Rotate the SSL certificate"),
		("Emergency", "High", "Rolled Back", "Emergency firewall rule change"),
		("Standard", "Low", "Successful with Issues", "Monthly patch window"),
	):
		start = add_days(now, -random.randint(5, 45))
		doc = frappe.get_doc({
			"doctype": "Change Request",
			"title": f"{DEMO_PREFIX} {title}",
			"change_type": change_type,
			"risk": risk,
			"status": "Draft",
			"business_justification": "Demo change created by the seeder.",
			"implementation_plan": "Apply the change during the approved window.",
			"rollback_plan": "Restore the previous configuration from backup.",
			"testing_plan": "Smoke test the affected services.",
			"planned_start": start,
			"planned_end": add_to_date(start, hours=3),
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Change Request", doc.name, {
			"status": "Rolled Back" if result == "Rolled Back" else "Completed",
			"validation_result": result,
			"actual_start": start,
			"actual_end": add_to_date(start, hours=random.randint(1, 5)),
			"rollback_reason": "Demo rollback." if result == "Rolled Back" else None,
			"approval_status": "Approved",
		}, update_modified=False)

	for title, article_type, category in (
		("How to reset your Office365 password", "How-To", "Office365"),
		("VPN troubleshooting checklist", "Troubleshooting", "Networking"),
		("Requesting a new laptop", "FAQ", "Infrastructure"),
	):
		frappe.get_doc({
			"doctype": "Knowledge Article",
			"title": f"{DEMO_PREFIX} {title}",
			"article_type": article_type,
			"status": "Published",
			"category": category,
			"content": f"<p>Demo article: {title}.</p>",
			"view_count": random.randint(5, 300),
			"helpful_count": random.randint(1, 40),
			"not_helpful_count": random.randint(0, 6),
		}).insert(ignore_permissions=True)


def purge():
	"""Remove everything the seeder created."""
	frappe.flags.in_migrate = True

	tickets = frappe.get_all("Service Ticket", filters={"tags": DEMO_TAG}, pluck="name")
	for child in ("Ticket Feedback", "Ticket Comment", "Work Log"):
		for name in frappe.get_all(child, filters={"ticket": ["in", tickets or [""]]},
		                           pluck="name"):
			frappe.delete_doc(child, name, force=1, ignore_permissions=True,
			                  delete_permanently=True)

	for name in tickets:
		frappe.delete_doc("Service Ticket", name, force=1, ignore_permissions=True,
		                  delete_permanently=True)
		frappe.db.delete("Service Desk Audit Log", {"reference_name": name})

	for doctype in ("Incident", "Problem", "Change Request", "Knowledge Article"):
		for name in frappe.get_all(doctype, filters={"title": ["like", f"{DEMO_PREFIX}%"]},
		                           pluck="name"):
			frappe.delete_doc(doctype, name, force=1, ignore_permissions=True,
			                  delete_permanently=True)
			frappe.db.delete("Service Desk Audit Log", {"reference_name": name})

	frappe.db.commit()
	print(f"purged {len(tickets)} demo tickets and the related ITIL records")
