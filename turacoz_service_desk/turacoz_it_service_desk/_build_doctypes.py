"""One-shot DocType builder for the Turacoz IT Service Desk module.

Run with:
    bench --site <site> execute turacoz_service_desk.turacoz_it_service_desk._build_doctypes.run

With developer_mode on, inserting a DocType exports its JSON into
apps/tms/tms/turacoz_it_service_desk/doctype/<name>/. Those JSON files are the
source of truth afterwards; this module is only the scaffolding that produced
them and is safe to re-run (existing DocTypes are skipped unless force=True).
"""

import frappe

MODULE = "Turacoz IT Service Desk"

PRIORITIES = "Low\nMedium\nHigh\nCritical"
IMPACT_URGENCY = "Low\nMedium\nHigh"
SEVERITIES = "S1 - Critical\nS2 - High\nS3 - Medium\nS4 - Low"
TICKET_STATUSES = (
	"Draft\nOpen\nAssigned\nIn Progress\nPending User\nPending Vendor\n"
	"Testing\nResolved\nUser Verification\nClosed\nReopened\nCancelled"
)
RISK_LEVELS = "Low\nMedium\nHigh\nCritical"

# roles created by turacoz_service_desk.turacoz_it_service_desk.setup.install
R_EMPLOYEE = "Employee"
R_EXEC = "Service Desk Executive"
R_ENGINEER = "Service Desk Engineer"
R_LEAD = "Service Desk Team Lead"
R_DEPT = "Department Head"
R_MANAGER = "IT Manager"
R_CISO = "CISO"
R_AUDITOR = "Auditor"
R_SYS = "System Manager"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def f(fieldname, fieldtype, label=None, **kw):
	d = {"fieldname": fieldname, "fieldtype": fieldtype}
	if label is not None:
		d["label"] = label
	d.update(kw)
	return d


def sb(fieldname, label=None, **kw):
	return f(fieldname, "Section Break", label, **kw)


def cb(fieldname="cb_" + "x"):
	return f(fieldname, "Column Break")


def P(role, read=1, write=0, create=0, delete=0, submit=0, cancel=0, amend=0,
      report=1, export=0, share=0, print_=1, email=1, if_owner=0):
	return {
		"role": role, "read": read, "write": write, "create": create,
		"delete": delete, "submit": submit, "cancel": cancel, "amend": amend,
		"report": report, "export": export, "share": share, "print": print_,
		"email": email, "if_owner": if_owner,
	}


def full_access(role):
	return P(role, write=1, create=1, delete=1, export=1, share=1)


def rw(role):
	return P(role, write=1, create=1, share=1)


ADMIN_PERMS = [full_access(R_SYS), full_access(R_MANAGER)]
READ_ONLY_AUDIT = P(R_AUDITOR, read=1, report=1, export=1)


def doctype(name, fields, permissions=None, istable=0, issingle=0, autoname=None,
            title_field=None, search_fields=None, sort_field=None, sort_order="DESC",
            track_changes=1, is_submittable=0, quick_entry=0, editable_grid=1,
            allow_rename=0, description=None, naming_rule=None, translated_doctype=0,
            show_name_in_global_search=0, track_seen=0):
	d = {
		"doctype": "DocType",
		"name": name,
		"module": MODULE,
		"custom": 0,
		"istable": istable,
		"issingle": issingle,
		"editable_grid": editable_grid,
		"engine": "InnoDB",
		"fields": fields,
		"permissions": [] if istable else (permissions or ADMIN_PERMS),
	}
	if not istable and not issingle:
		d["track_changes"] = track_changes
		d["allow_rename"] = allow_rename
		d["show_name_in_global_search"] = show_name_in_global_search
		if track_seen:
			d["track_seen"] = 1
	if autoname:
		d["autoname"] = autoname
	if naming_rule:
		d["naming_rule"] = naming_rule
	if title_field:
		d["title_field"] = title_field
	if search_fields:
		d["search_fields"] = search_fields
	if sort_field:
		d["sort_field"] = sort_field
		d["sort_order"] = sort_order
	if is_submittable:
		d["is_submittable"] = 1
	if quick_entry:
		d["quick_entry"] = 1
	if description:
		d["description"] = description
	return d


# ---------------------------------------------------------------------------
# child tables
# ---------------------------------------------------------------------------

def child_tables_a():
	out = []

	out.append(doctype("Service Desk Team Member", istable=1, fields=[
		f("user", "Link", "User", options="User", reqd=1, in_list_view=1, columns=3),
		f("full_name", "Data", "Full Name", fetch_from="user.full_name", read_only=1, in_list_view=1, columns=2),
		f("role_in_team", "Select", "Role In Team", options="Member\nLead\nBackup", default="Member",
		  in_list_view=1, columns=2),
		f("max_open_tickets", "Int", "Max Open Tickets", default="20", in_list_view=1, columns=2,
		  description="Load balancing cap. 0 means unlimited."),
		f("is_available", "Check", "Available", default="1", in_list_view=1, columns=1),
	]))

	out.append(doctype("Service Catalog Document", istable=1, fields=[
		f("document_name", "Data", "Document", reqd=1, in_list_view=1, columns=4),
		f("is_mandatory", "Check", "Mandatory", default="1", in_list_view=1, columns=1),
		f("description", "Small Text", "Description", in_list_view=1, columns=5),
	]))

	out.append(doctype("SLA Priority Rule", istable=1, fields=[
		f("priority", "Select", "Priority", options=PRIORITIES, reqd=1, in_list_view=1, columns=2),
		f("response_time", "Duration", "Response Time", reqd=1, in_list_view=1, columns=3,
		  description="Time allowed for first response."),
		f("resolution_time", "Duration", "Resolution Time", reqd=1, in_list_view=1, columns=3,
		  description="Time allowed to reach Resolved."),
	]))

	out.append(doctype("SLA Working Day", istable=1, fields=[
		f("workday", "Select", "Workday", reqd=1, in_list_view=1, columns=3,
		  options="Monday\nTuesday\nWednesday\nThursday\nFriday\nSaturday\nSunday"),
		f("start_time", "Time", "Start Time", reqd=1, in_list_view=1, columns=3, default="09:00:00"),
		f("end_time", "Time", "End Time", reqd=1, in_list_view=1, columns=3, default="18:00:00"),
	]))

	out.append(doctype("SLA Escalation Rule", istable=1, fields=[
		f("escalation_type", "Select", "Applies To", options="Response\nResolution", default="Resolution",
		  reqd=1, in_list_view=1, columns=2),
		f("after_percent", "Percent", "Trigger At % Elapsed", default="75", reqd=1, in_list_view=1, columns=2,
		  description="Fire when this much of the SLA window has been consumed."),
		f("escalate_to_role", "Link", "Escalate To Role", options="Role", in_list_view=1, columns=2),
		f("escalate_to_user", "Link", "Escalate To User", options="User", in_list_view=1, columns=2),
		f("increase_priority", "Check", "Raise Priority", default="0", in_list_view=1, columns=1),
		f("notify_requester", "Check", "Notify Requester", default="0", in_list_view=1, columns=1),
	]))

	out.append(doctype("SLA Pause Status", istable=1, fields=[
		f("status", "Select", "Status", options=TICKET_STATUSES, reqd=1, in_list_view=1, columns=4),
		f("description", "Small Text", "Why", in_list_view=1, columns=6),
	]))

	out.append(doctype("Ticket Timeline", istable=1, fields=[
		f("event_time", "Datetime", "Time", reqd=1, in_list_view=1, columns=2),
		f("event_type", "Select", "Event", in_list_view=1, columns=2,
		  options=("Created\nStatus Change\nAssignment\nComment\nApproval\nSLA\nAttachment\n"
		           "Work Log\nEscalation\nLinked Record\nOther")),
		f("user", "Link", "User", options="User", in_list_view=1, columns=2),
		f("description", "Small Text", "Description", in_list_view=1, columns=4),
		f("from_value", "Data", "From"),
		f("to_value", "Data", "To"),
	]))

	out.append(doctype("Ticket Watcher", istable=1, fields=[
		f("user", "Link", "User", options="User", reqd=1, in_list_view=1, columns=5),
		f("notify_on", "Select", "Notify On", default="All Updates", in_list_view=1, columns=5,
		  options="All Updates\nStatus Change\nResolution Only"),
	]))

	out.append(doctype("SLA Event", istable=1, fields=[
		f("event", "Select", "Event", in_list_view=1, columns=3,
		  options=("SLA Applied\nResponse Met\nResponse Breached\nResolution Met\nResolution Breached\n"
		           "Paused\nResumed\nEscalated\nReset")),
		f("event_time", "Datetime", "Time", in_list_view=1, columns=3),
		f("details", "Small Text", "Details", in_list_view=1, columns=6),
	]))

	out.append(doctype("Approval History", istable=1, fields=[
		f("approval_level", "Int", "Level", in_list_view=1, columns=1),
		f("approver", "Link", "Approver", options="User", in_list_view=1, columns=2),
		f("approver_role", "Link", "Role", options="Role", in_list_view=1, columns=2),
		f("status", "Select", "Status", options="Pending\nApproved\nRejected\nSkipped", default="Pending",
		  in_list_view=1, columns=2),
		f("action_on", "Datetime", "Action On", in_list_view=1, columns=2),
		f("comments", "Small Text", "Comments", in_list_view=1, columns=3),
	]))

	out.append(doctype("Related Record", istable=1, fields=[
		f("reference_doctype", "Link", "Type", options="DocType", reqd=1, in_list_view=1, columns=3),
		f("reference_name", "Dynamic Link", "Record", options="reference_doctype", reqd=1,
		  in_list_view=1, columns=3),
		f("relationship", "Select", "Relationship", default="Related", in_list_view=1, columns=2,
		  options="Related\nDuplicate Of\nCaused By\nBlocks\nBlocked By\nParent Of\nChild Of"),
		f("notes", "Small Text", "Notes", in_list_view=1, columns=4),
	]))

	out.append(doctype("Notification Sent", istable=1, fields=[
		f("channel", "Select", "Channel", options="Email\nSystem\nSMS\nTeams\nWhatsApp", default="Email",
		  in_list_view=1, columns=2),
		f("recipient", "Data", "Recipient", in_list_view=1, columns=3),
		f("trigger_event", "Data", "Trigger", in_list_view=1, columns=2),
		f("sent_on", "Datetime", "Sent On", in_list_view=1, columns=2),
		f("status", "Select", "Status", options="Sent\nFailed", default="Sent", in_list_view=1, columns=1),
		f("subject", "Data", "Subject"),
		f("error", "Small Text", "Error"),
	]))

	out.append(doctype("Approval Matrix Level", istable=1, fields=[
		f("level", "Int", "Level", reqd=1, in_list_view=1, columns=1),
		f("approver_type", "Select", "Approver Type", reqd=1, default="Role", in_list_view=1, columns=2,
		  options=("Role\nSpecific User\nDepartment Head\nTeam Lead\nIT Manager\nCISO\nRequester Manager")),
		f("approver_role", "Link", "Role", options="Role", in_list_view=1, columns=2,
		  depends_on="eval:doc.approver_type=='Role'"),
		f("approver_user", "Link", "User", options="User", in_list_view=1, columns=2,
		  depends_on="eval:doc.approver_type=='Specific User'"),
		f("approval_mode", "Select", "Mode", options="Sequential\nParallel", default="Sequential",
		  in_list_view=1, columns=2),
		f("is_mandatory", "Check", "Mandatory", default="1", in_list_view=1, columns=1),
		f("condition", "Code", "Condition", options="Python",
		  description="Optional python expression evaluated against `doc`. Level is skipped when it is false."),
	]))

	out.append(doctype("Privileged Access Scope", istable=1, fields=[
		f("system", "Select", "System", reqd=1, in_list_view=1, columns=3,
		  options=("ERP Admin\nSSH\nFirewall\nVPN\nAzure\nAWS\nDatabase\nGitHub\nOffice365\n"
		           "Domain Admin\nOther")),
		f("target", "Data", "Target / Host", in_list_view=1, columns=4,
		  description="Server, database, repo or tenant the access applies to."),
		f("access_level", "Select", "Access Level", options="Read\nWrite\nAdmin\nRoot", default="Read",
		  in_list_view=1, columns=2),
		f("notes", "Small Text", "Notes", in_list_view=1, columns=3),
	]))

	return out


def child_tables_b():
	"""Child tables whose Link fields target masters, so they come after them."""
	out = []

	out.append(doctype("Assignment History", istable=1, fields=[
		f("assigned_to", "Link", "Assigned To", options="User", in_list_view=1, columns=3),
		f("team", "Link", "Team", options="Service Desk Team", in_list_view=1, columns=2),
		f("assigned_by", "Link", "Assigned By", options="User", in_list_view=1, columns=2),
		f("assigned_on", "Datetime", "Assigned On", in_list_view=1, columns=2),
		f("reason", "Small Text", "Reason", in_list_view=1, columns=3),
	]))

	out.append(doctype("Change Affected Service", istable=1, fields=[
		f("configuration_item", "Link", "Configuration Item", options="Configuration Item",
		  in_list_view=1, columns=3),
		f("service_name", "Data", "Service", in_list_view=1, columns=3),
		f("downtime_required", "Check", "Downtime", default="0", in_list_view=1, columns=1),
		f("impact_notes", "Small Text", "Impact", in_list_view=1, columns=4),
	]))

	return out


# ---------------------------------------------------------------------------
# masters
# ---------------------------------------------------------------------------

def masters():
	out = []

	out.append(doctype(
		"Service Desk Team", autoname="field:team_name", title_field="team_name",
		search_fields="team_lead", sort_field="modified",
		permissions=ADMIN_PERMS + [rw(R_LEAD), P(R_EXEC), P(R_ENGINEER), READ_ONLY_AUDIT],
		fields=[
			f("team_name", "Data", "Team Name", reqd=1, unique=1, in_list_view=1),
			f("team_lead", "Link", "Team Lead", options="User", reqd=1, in_list_view=1),
			f("email", "Data", "Team Email", options="Email"),
			cb("cb_team_1"),
			f("assignment_method", "Select", "Assignment Method", default="Round Robin", in_list_view=1,
			  options="Round Robin\nLoad Balancing\nSkill Based\nManual",
			  description="How the assignment engine picks an engineer from this team."),
			f("is_active", "Check", "Active", default="1", in_list_view=1),
			f("escalation_user", "Link", "Escalation Contact", options="User"),
			sb("sb_team_members", "Members"),
			f("members", "Table", "Members", options="Service Desk Team Member"),
			sb("sb_team_desc"),
			f("description", "Small Text", "Description"),
		]))

	out.append(doctype(
		"SLA Policy", autoname="field:policy_name", title_field="policy_name", sort_field="modified",
		permissions=ADMIN_PERMS + [P(R_LEAD), P(R_EXEC), P(R_ENGINEER), READ_ONLY_AUDIT],
		fields=[
			f("policy_name", "Data", "Policy Name", reqd=1, unique=1, in_list_view=1),
			f("is_default", "Check", "Default Policy", default="0", in_list_view=1,
			  description="Used when no category or service supplies a policy."),
			f("is_active", "Check", "Active", default="1", in_list_view=1),
			cb("cb_sla_1"),
			f("holiday_list", "Link", "Holiday List", options="Holiday List",
			  description="Holidays are excluded from SLA elapsed time."),
			f("apply_24x7", "Check", "24x7 (ignore working hours)", default="0"),
			sb("sb_sla_priority", "Response & Resolution Targets"),
			f("priority_rules", "Table", "Priority Rules", options="SLA Priority Rule", reqd=1),
			sb("sb_sla_hours", "Business Hours", depends_on="eval:!doc.apply_24x7"),
			f("working_days", "Table", "Working Days", options="SLA Working Day"),
			sb("sb_sla_pause", "Pause Conditions"),
			f("pause_statuses", "Table", "Pause On These Statuses", options="SLA Pause Status",
			  description="The SLA clock stops while the ticket sits in any of these statuses and resumes on exit."),
			sb("sb_sla_esc", "Escalation"),
			f("escalation_rules", "Table", "Escalation Rules", options="SLA Escalation Rule"),
			sb("sb_sla_desc"),
			f("description", "Small Text", "Description"),
		]))

	out.append(doctype(
		"Approval Matrix", autoname="field:matrix_name", title_field="matrix_name", sort_field="modified",
		permissions=ADMIN_PERMS + [P(R_LEAD), P(R_DEPT), P(R_CISO), READ_ONLY_AUDIT],
		fields=[
			f("matrix_name", "Data", "Matrix Name", reqd=1, unique=1, in_list_view=1),
			f("applies_to", "Select", "Applies To", reqd=1, default="Service Ticket", in_list_view=1,
			  options="Service Ticket\nChange Request\nPrivileged Access Request\nService Catalog"),
			f("is_active", "Check", "Active", default="1", in_list_view=1),
			cb("cb_am_1"),
			f("approval_mode", "Select", "Approval Mode", default="Sequential", in_list_view=1,
			  options="Sequential\nParallel"),
			f("department", "Link", "Department", options="Department"),
			sb("sb_am_cond", "Match Conditions"),
			f("priority", "Select", "Priority", options="\n" + PRIORITIES),
			f("risk_level", "Select", "Risk Level", options="\n" + RISK_LEVELS),
			cb("cb_am_2"),
			f("min_amount", "Currency", "Minimum Amount"),
			f("max_amount", "Currency", "Maximum Amount"),
			sb("sb_am_levels", "Approval Levels"),
			f("levels", "Table", "Levels", options="Approval Matrix Level", reqd=1),
		]))

	out.append(doctype(
		"IT Service Category", autoname="field:category_name", title_field="category_name",
		sort_field="modified", quick_entry=1,
		permissions=ADMIN_PERMS + [rw(R_LEAD), P(R_EXEC), P(R_ENGINEER), P(R_EMPLOYEE), READ_ONLY_AUDIT],
		fields=[
			f("category_name", "Data", "Category Name", reqd=1, unique=1, in_list_view=1),
			f("parent_service_category", "Link", "Parent Category", options="IT Service Category",
			  in_list_view=1, description="Leave blank for a top level category."),
			f("is_group", "Check", "Is Group", default="0", in_list_view=1),
			f("is_active", "Check", "Active", default="1", in_list_view=1),
			cb("cb_cat_1"),
			f("default_priority", "Select", "Default Priority", options="\n" + PRIORITIES, default="Medium"),
			f("default_impact", "Select", "Default Impact", options="\n" + IMPACT_URGENCY),
			f("default_urgency", "Select", "Default Urgency", options="\n" + IMPACT_URGENCY),
			sb("sb_cat_routing", "Routing Defaults"),
			f("default_team", "Link", "Default Team", options="Service Desk Team"),
			f("default_engineer", "Link", "Default Engineer", options="User"),
			cb("cb_cat_2"),
			f("default_sla_policy", "Link", "Default SLA Policy", options="SLA Policy"),
			f("requires_approval", "Check", "Requires Approval", default="0"),
			sb("sb_cat_desc"),
			f("description", "Small Text", "Description"),
		]))

	return out


def masters_late():
	"""Masters that reference IT Service Category and therefore come after it."""
	out = []

	out.append(doctype(
		"Engineer Skill", autoname="format:SKL-{engineer}-{category}", sort_field="modified",
		permissions=ADMIN_PERMS + [rw(R_LEAD), P(R_EXEC), P(R_ENGINEER), READ_ONLY_AUDIT],
		fields=[
			f("engineer", "Link", "Engineer", options="User", reqd=1, in_list_view=1),
			f("category", "Link", "Category", options="IT Service Category", reqd=1, in_list_view=1),
			cb("cb_skill_1"),
			f("skill_level", "Select", "Skill Level", options="Beginner\nIntermediate\nExpert",
			  default="Intermediate", reqd=1, in_list_view=1),
			f("is_certified", "Check", "Certified", default="0", in_list_view=1),
			f("is_active", "Check", "Active", default="1"),
			sb("sb_skill_notes"),
			f("notes", "Small Text", "Notes"),
		]))

	out.append(doctype(
		"Configuration Item", autoname="field:ci_name", title_field="ci_name", sort_field="modified",
		search_fields="ci_type,environment,hostname",
		permissions=ADMIN_PERMS + [rw(R_LEAD), rw(R_ENGINEER), P(R_EXEC), P(R_CISO), READ_ONLY_AUDIT],
		fields=[
			f("ci_name", "Data", "Name", reqd=1, unique=1, in_list_view=1),
			f("ci_type", "Select", "Type", reqd=1, in_list_view=1,
			  options=("Server\nApplication\nDatabase\nWebsite\nAPI\nFirewall\nStorage\nNetwork Device\n"
			           "Cloud VM\nLicense\nOther")),
			f("environment", "Select", "Environment", options="Production\nUAT\nDevelopment\nDR",
			  default="Production", reqd=1, in_list_view=1),
			f("status", "Select", "Status", options="Active\nInactive\nUnder Maintenance\nRetired",
			  default="Active", in_list_view=1),
			cb("cb_ci_1"),
			f("criticality", "Select", "Criticality", options=RISK_LEVELS, default="Medium", in_list_view=1),
			f("owner_user", "Link", "Owner", options="User"),
			f("support_team", "Link", "Support Team", options="Service Desk Team"),
			f("linked_asset", "Link", "ERP Asset", options="Asset",
			  description="Links this CI to the ERPNext Asset register."),
			sb("sb_ci_tech", "Technical"),
			f("hostname", "Data", "Hostname"),
			f("ip_address", "Data", "IP Address"),
			f("operating_system", "Data", "Operating System"),
			cb("cb_ci_2"),
			f("location", "Data", "Location"),
			f("vendor", "Link", "Vendor", options="Supplier"),
			f("go_live_date", "Date", "Go Live Date"),
			f("warranty_expiry", "Date", "Warranty / AMC Expiry"),
			sb("sb_ci_desc"),
			f("description", "Text", "Description"),
		]))

	out.append(doctype(
		"Knowledge Article", autoname="naming_series:", title_field="title", sort_field="modified",
		search_fields="article_type,category,status", show_name_in_global_search=1,
		permissions=ADMIN_PERMS + [rw(R_LEAD), rw(R_ENGINEER), rw(R_EXEC), P(R_EMPLOYEE), READ_ONLY_AUDIT],
		fields=[
			f("naming_series", "Select", "Series", options="KB-.YYYY.-.#####", default="KB-.YYYY.-.#####",
			  reqd=1, hidden=1),
			f("title", "Data", "Title", reqd=1, in_list_view=1),
			f("article_type", "Select", "Type", reqd=1, default="How-To", in_list_view=1,
			  options="FAQ\nHow-To\nVideo\nPolicy\nSOP\nKnown Error\nTroubleshooting"),
			f("status", "Select", "Status", options="Draft\nUnder Review\nPublished\nArchived",
			  default="Draft", in_list_view=1),
			cb("cb_kb_1"),
			f("category", "Link", "Category", options="IT Service Category", in_list_view=1),
			f("sub_category", "Link", "Sub Category", options="IT Service Category"),
			f("is_public", "Check", "Visible On Portal", default="0"),
			f("version", "Int", "Version", default="1", read_only=1),
			sb("sb_kb_content", "Content"),
			f("content", "Text Editor", "Content"),
			f("video_url", "Data", "Video URL", depends_on="eval:doc.article_type=='Video'"),
			f("attachment", "Attach", "Attachment"),
			sb("sb_kb_meta", "Ownership & Approval"),
			f("author", "Link", "Author", options="User"),
			f("approved_by", "Link", "Approved By", options="User", read_only=1),
			f("approved_on", "Datetime", "Approved On", read_only=1),
			cb("cb_kb_2"),
			f("view_count", "Int", "Views", read_only=1, default="0"),
			f("helpful_count", "Int", "Marked Helpful", read_only=1, default="0"),
			f("not_helpful_count", "Int", "Marked Not Helpful", read_only=1, default="0"),
			f("keywords", "Small Text", "Keywords",
			  description="Comma separated. Used by the auto-suggestion engine."),
			sb("sb_kb_related", "Related Records"),
			f("related_records", "Table", "Related Records", options="Related Record"),
		]))

	out.append(doctype(
		"Service Catalog", autoname="field:service_name", title_field="service_name", sort_field="modified",
		search_fields="category,department",
		permissions=ADMIN_PERMS + [rw(R_LEAD), P(R_EXEC), P(R_ENGINEER), P(R_EMPLOYEE), READ_ONLY_AUDIT],
		fields=[
			f("service_name", "Data", "Service Name", reqd=1, unique=1, in_list_view=1),
			f("category", "Link", "Category", options="IT Service Category", reqd=1, in_list_view=1),
			f("sub_category", "Link", "Sub Category", options="IT Service Category"),
			f("is_active", "Check", "Active", default="1", in_list_view=1),
			cb("cb_svc_1"),
			f("default_priority", "Select", "Default Priority", options="\n" + PRIORITIES, default="Medium"),
			f("sla_policy", "Link", "SLA Policy", options="SLA Policy"),
			f("department", "Link", "Department", options="Department"),
			f("cost_center", "Link", "Cost Center", options="Cost Center"),
			f("estimated_cost", "Currency", "Estimated Cost"),
			sb("sb_svc_desc", "Description"),
			f("description", "Text Editor", "Description"),
			f("image", "Attach Image", "Icon"),
			sb("sb_svc_approval", "Approval"),
			f("approval_required", "Check", "Approval Required", default="0"),
			f("approval_matrix", "Link", "Approval Matrix", options="Approval Matrix",
			  depends_on="approval_required"),
			sb("sb_svc_docs", "Required Documents"),
			f("required_documents", "Table", "Required Documents", options="Service Catalog Document"),
		]))

	return out


# ---------------------------------------------------------------------------
# transactions
# ---------------------------------------------------------------------------

def transactions_a():
	"""Problem and Change Request. Problem.change_request is patched in later."""
	out = []

	out.append(doctype(
		"Problem", autoname="naming_series:", title_field="title", sort_field="modified",
		search_fields="status,priority,category", track_seen=1,
		permissions=ADMIN_PERMS + [rw(R_LEAD), rw(R_ENGINEER), P(R_EXEC), P(R_CISO), READ_ONLY_AUDIT],
		fields=[
			f("naming_series", "Select", "Series", options="PRB-.YYYY.-.#####", default="PRB-.YYYY.-.#####",
			  reqd=1, hidden=1),
			f("title", "Data", "Title", reqd=1, in_list_view=1),
			f("status", "Select", "Status", reqd=1, default="Open", in_list_view=1,
			  options="Open\nUnder Investigation\nKnown Error\nFix In Progress\nResolved\nClosed"),
			f("priority", "Select", "Priority", options=PRIORITIES, default="Medium", in_list_view=1),
			cb("cb_prb_1"),
			f("category", "Link", "Category", options="IT Service Category", in_list_view=1),
			f("assigned_to", "Link", "Assigned To", options="User", in_list_view=1),
			f("identified_on", "Date", "Identified On"),
			f("resolved_on", "Date", "Resolved On", read_only=1),
			f("is_known_error", "Check", "Known Error", default="0"),
			sb("sb_prb_desc", "Description"),
			f("description", "Text", "Description"),
			sb("sb_prb_analysis", "Analysis"),
			f("incident_count", "Int", "Linked Incident Count", read_only=1, default="0"),
			f("trend_analysis", "Text", "Trend Analysis"),
			f("root_cause", "Text", "Root Cause"),
			cb("cb_prb_2"),
			f("workaround", "Text", "Workaround"),
			f("permanent_fix", "Text", "Permanent Fix"),
			sb("sb_prb_closure", "Closure"),
			f("knowledge_article", "Link", "Knowledge Article", options="Knowledge Article"),
			f("closure_notes", "Text", "Closure Notes"),
			sb("sb_prb_related", "Related Records"),
			f("related_records", "Table", "Related Incidents & Tickets", options="Related Record"),
		]))

	out.append(doctype(
		"Change Request", autoname="naming_series:", title_field="title", sort_field="modified",
		search_fields="change_type,risk,status", track_seen=1,
		permissions=ADMIN_PERMS + [rw(R_LEAD), rw(R_ENGINEER), P(R_EXEC), P(R_DEPT), P(R_CISO), READ_ONLY_AUDIT],
		fields=[
			f("naming_series", "Select", "Series", options="CHG-.YYYY.-.#####", default="CHG-.YYYY.-.#####",
			  reqd=1, hidden=1),
			f("title", "Data", "Title", reqd=1, in_list_view=1),
			f("change_type", "Select", "Change Type", reqd=1, default="Normal", in_list_view=1,
			  options="Standard\nNormal\nEmergency"),
			f("risk", "Select", "Risk", reqd=1, default="Medium", in_list_view=1, options=RISK_LEVELS),
			f("status", "Select", "Status", reqd=1, default="Draft", in_list_view=1,
			  options=("Draft\nSubmitted\nRisk Review\nCAB Approval\nScheduled\nImplementation\n"
			           "Validation\nCompleted\nClosed\nRolled Back\nRejected\nCancelled")),
			cb("cb_chg_1"),
			f("priority", "Select", "Priority", options=PRIORITIES, default="Medium"),
			f("category", "Link", "Category", options="IT Service Category"),
			f("requested_by", "Link", "Requested By", options="User", reqd=1, in_list_view=1),
			f("change_owner", "Link", "Change Owner", options="User"),
			sb("sb_chg_just", "Justification & Plans"),
			f("business_justification", "Text", "Business Justification", reqd=1),
			f("implementation_plan", "Text", "Implementation Plan", reqd=1),
			f("rollback_plan", "Text", "Rollback Plan", reqd=1),
			f("testing_plan", "Text", "Testing Plan"),
			sb("sb_chg_impact", "Impact & Window"),
			f("downtime_required", "Check", "Downtime Required", default="0"),
			f("downtime_minutes", "Int", "Downtime (minutes)", depends_on="downtime_required"),
			f("planned_start", "Datetime", "Planned Start"),
			f("planned_end", "Datetime", "Planned End"),
			cb("cb_chg_2"),
			f("actual_start", "Datetime", "Actual Start", read_only=1),
			f("actual_end", "Datetime", "Actual End", read_only=1),
			f("affected_services", "Table", "Affected Services", options="Change Affected Service"),
			sb("sb_chg_approval", "Approval"),
			f("cab_required", "Check", "CAB Approval Required", default="0"),
			f("cab_date", "Date", "CAB Meeting Date", depends_on="cab_required"),
			f("approval_matrix", "Link", "Approval Matrix", options="Approval Matrix"),
			f("approval_status", "Select", "Approval Status", read_only=1, default="Not Required",
			  options="Not Required\nPending\nApproved\nRejected", in_list_view=1),
			f("current_approval_level", "Int", "Current Approval Level", read_only=1, default="0"),
			f("approvals", "Table", "Approvals", options="Approval History", read_only=1),
			sb("sb_chg_result", "Implementation Result"),
			f("implementation_notes", "Text", "Implementation Notes"),
			f("validation_result", "Select", "Validation Result",
			  options="\nSuccessful\nSuccessful with Issues\nFailed\nRolled Back"),
			f("rollback_reason", "Text", "Rollback Reason",
			  depends_on="eval:doc.validation_result=='Rolled Back' || doc.status=='Rolled Back'"),
			sb("sb_chg_related", "Related & Timeline"),
			f("related_records", "Table", "Related Records", options="Related Record"),
			f("timeline", "Table", "Timeline", options="Ticket Timeline", read_only=1),
		]))

	return out


def transactions_b():
	out = []

	out.append(doctype(
		"Incident", autoname="naming_series:", title_field="title", sort_field="modified",
		search_fields="incident_type,severity,status", track_seen=1,
		permissions=ADMIN_PERMS + [rw(R_LEAD), rw(R_ENGINEER), rw(R_CISO), P(R_EXEC), READ_ONLY_AUDIT],
		fields=[
			f("naming_series", "Select", "Series", options="INC-.YYYY.-.#####", default="INC-.YYYY.-.#####",
			  reqd=1, hidden=1),
			f("title", "Data", "Title", reqd=1, in_list_view=1),
			f("incident_type", "Select", "Incident Type", reqd=1, in_list_view=1,
			  options=("Outage\nDegradation\nSecurity\nData Breach\nData Loss\nMalware\nPhishing\n"
			           "Unauthorized Access\nHardware Failure\nOther")),
			f("severity", "Select", "Severity", reqd=1, default="S3 - Medium", in_list_view=1,
			  options=SEVERITIES),
			f("status", "Select", "Status", reqd=1, default="Open", in_list_view=1,
			  options="Open\nInvestigating\nContained\nMitigated\nResolved\nClosed"),
			cb("cb_inc_1"),
			f("is_security_incident", "Check", "Security Incident", default="0",
			  description="Security incidents are visible to the CISO role and included in security reports."),
			f("affected_service", "Link", "Affected Service (CI)", options="Configuration Item"),
			f("affected_users", "Int", "Affected Users"),
			f("reported_by", "Link", "Reported By", options="User"),
			f("incident_manager", "Link", "Incident Manager", options="User", in_list_view=1),
			f("problem", "Link", "Problem", options="Problem"),
			sb("sb_inc_times", "Timeline"),
			f("detection_time", "Datetime", "Detected At"),
			f("reported_time", "Datetime", "Reported At"),
			cb("cb_inc_2"),
			f("containment_time", "Datetime", "Contained At"),
			f("resolution_time", "Datetime", "Resolved At"),
			sb("sb_inc_impact", "Impact"),
			f("business_impact", "Text", "Business Impact"),
			sb("sb_inc_actions", "Response"),
			f("containment_actions", "Text", "Containment Actions"),
			f("resolution", "Text", "Resolution"),
			sb("sb_inc_rca", "Root Cause Analysis"),
			f("root_cause", "Text", "Root Cause"),
			f("lessons_learned", "Text", "Lessons Learned"),
			cb("cb_inc_3"),
			f("capa", "Text", "Corrective & Preventive Action (CAPA)"),
			f("rca_document", "Attach", "RCA Document"),
			sb("sb_inc_related", "Related & Timeline"),
			f("related_records", "Table", "Related Tickets", options="Related Record"),
			f("timeline", "Table", "Timeline", options="Ticket Timeline", read_only=1),
		]))

	return out


def service_ticket():
	return doctype(
		"Service Ticket", autoname="naming_series:", title_field="subject", sort_field="modified",
		search_fields="status,priority,assigned_engineer,category", track_seen=1,
		show_name_in_global_search=1,
		permissions=[
			full_access(R_SYS), full_access(R_MANAGER),
			rw(R_LEAD), rw(R_ENGINEER), rw(R_EXEC),
			P(R_EMPLOYEE, read=1, write=1, create=1, if_owner=1, share=1),
			P(R_DEPT), P(R_CISO), READ_ONLY_AUDIT,
		],
		fields=[
			f("naming_series", "Select", "Series", options="TKT-.YYYY.-.######",
			  default="TKT-.YYYY.-.######", reqd=1, hidden=1),
			f("subject", "Data", "Subject", reqd=1, in_list_view=1, in_global_search=1),
			f("ticket_type", "Select", "Ticket Type", reqd=1, default="Service Request", in_list_view=1,
			  options="Incident\nService Request\nChange Request\nProblem\nQuery"),
			f("status", "Select", "Status", reqd=1, default="Open", in_list_view=1,
			  in_standard_filter=1, options=TICKET_STATUSES, search_index=1),
			f("priority", "Select", "Priority", reqd=1, default="Medium", in_list_view=1,
			  in_standard_filter=1, options=PRIORITIES),
			cb("cb_tkt_1"),
			f("service", "Link", "Service (Catalog)", options="Service Catalog"),
			f("category", "Link", "Category", options="IT Service Category", reqd=1, in_standard_filter=1),
			f("sub_category", "Link", "Sub Category", options="IT Service Category"),
			f("source", "Select", "Source", default="Portal",
			  options="Portal\nEmail\nPhone\nChat\nWalk-in\nAPI\nAuto"),
			f("department", "Link", "Department", options="Department"),

			sb("sb_tkt_people", "Requester"),
			f("requester", "Link", "Requester", options="User", reqd=1, in_standard_filter=1),
			f("requester_name", "Data", "Requester Name", fetch_from="requester.full_name", read_only=1),
			f("requested_for", "Link", "Requested For", options="User",
			  description="Set when raising a ticket on behalf of someone else."),
			cb("cb_tkt_2"),
			f("contact_number", "Data", "Contact Number"),
			f("requester_employee", "Link", "Employee", options="Employee"),

			sb("sb_tkt_assign", "Assignment"),
			f("assigned_team", "Link", "Assigned Team", options="Service Desk Team", in_standard_filter=1),
			f("assigned_engineer", "Link", "Assigned Engineer", options="User", in_list_view=1,
			  in_standard_filter=1),
			f("engineer_name", "Data", "Engineer Name", fetch_from="assigned_engineer.full_name",
			  read_only=1),
			cb("cb_tkt_3"),
			f("impact", "Select", "Impact", options=IMPACT_URGENCY, default="Medium"),
			f("urgency", "Select", "Urgency", options=IMPACT_URGENCY, default="Medium"),
			f("severity", "Select", "Severity", options="\n" + SEVERITIES),

			sb("sb_tkt_desc", "Description"),
			f("short_description", "Small Text", "Short Description"),
			f("description", "Text Editor", "Detailed Description"),

			sb("sb_tkt_sla", "SLA", collapsible=1),
			f("sla_policy", "Link", "SLA Policy", options="SLA Policy", read_only=1),
			f("sla_status", "Select", "SLA Status", read_only=1, default="Ongoing", in_list_view=1,
			  options=("Ongoing\nPaused\nFulfilled\nFailed\nResponse Overdue\nResolution Overdue\n"
			           "Not Applicable")),
			f("response_by", "Datetime", "Respond By", read_only=1),
			f("resolution_by", "Datetime", "Resolve By", read_only=1),
			f("first_responded_on", "Datetime", "First Responded On", read_only=1),
			cb("cb_tkt_4"),
			f("response_sla_met", "Check", "Response SLA Met", read_only=1, default="0"),
			f("resolution_sla_met", "Check", "Resolution SLA Met", read_only=1, default="0"),
			f("total_hold_time", "Duration", "Total Hold Time", read_only=1, default="0"),
			f("hold_started_on", "Datetime", "Hold Started On", read_only=1, hidden=1),
			f("is_escalated", "Check", "Escalated", read_only=1, default="0"),
			f("escalation_level", "Int", "Escalation Level", read_only=1, default="0"),

			sb("sb_tkt_dates", "Dates", collapsible=1),
			f("opened_on", "Datetime", "Opened On", read_only=1),
			f("resolved_on", "Datetime", "Resolved On", read_only=1),
			cb("cb_tkt_5"),
			f("closed_on", "Datetime", "Closed On", read_only=1),
			f("reopened_on", "Datetime", "Last Reopened On", read_only=1),
			f("reopen_count", "Int", "Reopen Count", read_only=1, default="0"),

			sb("sb_tkt_approval", "Approval", collapsible=1,
			   depends_on="eval:doc.approval_status && doc.approval_status!='Not Required'"),
			f("approval_status", "Select", "Approval Status", read_only=1, default="Not Required",
			  options="Not Required\nPending\nApproved\nRejected"),
			f("approval_matrix", "Link", "Approval Matrix", options="Approval Matrix", read_only=1),
			f("current_approval_level", "Int", "Current Level", read_only=1, default="0"),
			f("approvals", "Table", "Approvals", options="Approval History", read_only=1),

			sb("sb_tkt_resolution", "Resolution", collapsible=1),
			f("root_cause", "Text", "Root Cause"),
			f("resolution", "Text Editor", "Resolution"),
			f("resolution_category", "Select", "Resolution Category",
			  options=("\nFixed\nWorkaround Provided\nConfiguration Change\nUser Education\n"
			           "No Fault Found\nDuplicate\nCancelled")),
			f("knowledge_article", "Link", "Knowledge Article Used", options="Knowledge Article"),

			sb("sb_tkt_feedback", "Feedback", collapsible=1),
			f("feedback_rating", "Rating", "Rating", read_only=1),
			f("feedback_comments", "Small Text", "Feedback Comments", read_only=1),

			sb("sb_tkt_links", "Linked Records", collapsible=1),
			f("linked_asset", "Link", "Asset", options="Asset"),
			f("configuration_item", "Link", "Configuration Item", options="Configuration Item"),
			f("linked_project", "Link", "Project", options="Project"),
			cb("cb_tkt_6"),
			f("linked_incident", "Link", "Incident", options="Incident"),
			f("linked_problem", "Link", "Problem", options="Problem"),
			f("linked_change", "Link", "Change Request", options="Change Request"),

			sb("sb_tkt_more_links", "Assets & Related", collapsible=1),
			f("asset_links", "Table", "Additional Assets", options="Ticket Asset Link"),
			f("related_records", "Table", "Related Records", options="Related Record"),
			f("watchers", "Table", "Watchers", options="Ticket Watcher"),

			sb("sb_tkt_audit", "History", collapsible=1),
			f("timeline", "Table", "Timeline", options="Ticket Timeline", read_only=1),
			f("sla_events", "Table", "SLA Events", options="SLA Event", read_only=1),
			f("assignment_history", "Table", "Assignment History", options="Assignment History",
			  read_only=1),
			f("notifications_sent", "Table", "Notifications Sent", options="Notification Sent",
			  read_only=1),

			sb("sb_tkt_meta", "Metrics", collapsible=1),
			f("total_worked_hours", "Float", "Total Worked Hours", read_only=1, default="0",
			  precision="2"),
			f("tags", "Data", "Tags", description="Comma separated."),
		])


def transactions_c():
	out = []

	out.append(doctype(
		"Ticket Asset Link", istable=1, fields=[
			f("asset", "Link", "Asset", options="Asset", in_list_view=1, columns=3),
			f("asset_name", "Data", "Asset Name", fetch_from="asset.asset_name", read_only=1,
			  in_list_view=1, columns=3),
			f("configuration_item", "Link", "Configuration Item", options="Configuration Item",
			  in_list_view=1, columns=3),
			f("notes", "Small Text", "Notes", in_list_view=1, columns=3),
		]))

	return out


def transactions_d():
	out = []

	out.append(doctype(
		"Work Log", autoname="naming_series:", sort_field="modified", search_fields="ticket,engineer",
		permissions=ADMIN_PERMS + [rw(R_LEAD), rw(R_ENGINEER), rw(R_EXEC), READ_ONLY_AUDIT],
		fields=[
			f("naming_series", "Select", "Series", options="WL-.YYYY.-.#####", default="WL-.YYYY.-.#####",
			  reqd=1, hidden=1),
			f("ticket", "Link", "Ticket", options="Service Ticket", reqd=1, in_list_view=1,
			  in_standard_filter=1),
			f("engineer", "Link", "Engineer", options="User", reqd=1, in_list_view=1,
			  in_standard_filter=1),
			f("activity_type", "Select", "Activity", default="Diagnosis", in_list_view=1,
			  options="Diagnosis\nImplementation\nTesting\nCommunication\nDocumentation\nTravel\nOther"),
			cb("cb_wl_1"),
			f("start_time", "Datetime", "Start Time", reqd=1, in_list_view=1),
			f("end_time", "Datetime", "End Time"),
			f("hours", "Float", "Hours", read_only=1, precision="2", in_list_view=1),
			f("is_billable", "Check", "Billable", default="0"),
			f("is_internal", "Check", "Internal Only", default="0",
			  description="Internal work logs are hidden from the requester on the portal."),
			sb("sb_wl_desc"),
			f("description", "Text", "Description", reqd=1),
			f("attachment", "Attach", "Attachment"),
		]))

	out.append(doctype(
		"Ticket Comment", autoname="hash", sort_field="creation",
		permissions=ADMIN_PERMS + [rw(R_LEAD), rw(R_ENGINEER), rw(R_EXEC),
		                           P(R_EMPLOYEE, read=1, write=1, create=1, if_owner=1), READ_ONLY_AUDIT],
		fields=[
			f("ticket", "Link", "Ticket", options="Service Ticket", reqd=1, in_list_view=1,
			  in_standard_filter=1),
			f("comment_by", "Link", "Comment By", options="User", reqd=1, in_list_view=1),
			f("comment_type", "Select", "Type", options="Public Note\nInternal Note", default="Public Note",
			  reqd=1, in_list_view=1),
			f("commented_on", "Datetime", "Commented On", read_only=1),
			sb("sb_cmt_content"),
			f("content", "Text Editor", "Comment", reqd=1),
			f("attachment", "Attach", "Attachment"),
		]))

	out.append(doctype(
		"Ticket Feedback", autoname="format:FB-{ticket}", sort_field="modified",
		permissions=ADMIN_PERMS + [P(R_LEAD), P(R_ENGINEER), P(R_EXEC),
		                           P(R_EMPLOYEE, read=1, write=1, create=1, if_owner=1), READ_ONLY_AUDIT],
		fields=[
			f("ticket", "Link", "Ticket", options="Service Ticket", reqd=1, unique=1, in_list_view=1),
			f("requester", "Link", "Requester", options="User", read_only=1, in_list_view=1),
			f("submitted_on", "Datetime", "Submitted On", read_only=1),
			cb("cb_fb_1"),
			f("rating", "Rating", "Overall Rating", reqd=1, in_list_view=1),
			f("would_recommend", "Check", "Would Recommend", default="1"),
			sb("sb_fb_detail", "Detailed Ratings"),
			f("response_speed", "Rating", "Response Speed"),
			f("resolution_quality", "Rating", "Resolution Quality"),
			cb("cb_fb_2"),
			f("engineer_courtesy", "Rating", "Engineer Courtesy"),
			sb("sb_fb_comments"),
			f("comments", "Small Text", "Comments"),
		]))

	out.append(doctype(
		"Privileged Access Request", autoname="naming_series:", sort_field="modified",
		search_fields="requester,request_type,status", track_seen=1,
		permissions=[
			full_access(R_SYS), full_access(R_MANAGER), full_access(R_CISO),
			rw(R_LEAD), P(R_ENGINEER),
			P(R_EMPLOYEE, read=1, write=1, create=1, if_owner=1),
			P(R_DEPT), READ_ONLY_AUDIT,
		],
		fields=[
			f("naming_series", "Select", "Series", options="PAR-.YYYY.-.#####",
			  default="PAR-.YYYY.-.#####", reqd=1, hidden=1),
			f("requester", "Link", "Requester", options="User", reqd=1, in_list_view=1),
			f("requested_for", "Link", "Requested For", options="User", in_list_view=1),
			f("request_type", "Select", "Primary Access Type", reqd=1, in_list_view=1,
			  options=("ERP Admin\nSSH\nFirewall\nVPN\nAzure\nAWS\nDatabase\nGitHub\nOffice365\n"
			           "Domain Admin\nOther")),
			f("status", "Select", "Status", reqd=1, default="Draft", in_list_view=1,
			  options=("Draft\nPending Approval\nApproved\nActive\nExpired\nRevoked\nRejected\n"
			           "Cancelled")),
			cb("cb_par_1"),
			f("ticket", "Link", "Related Ticket", options="Service Ticket"),
			f("valid_from", "Datetime", "Valid From", reqd=1),
			f("valid_till", "Datetime", "Valid Till", reqd=1,
			  description="Access is revoked automatically at this time when Auto Revoke is on."),
			f("auto_revoke", "Check", "Auto Revoke On Expiry", default="1"),
			sb("sb_par_scope", "Access Scope"),
			f("access_scope", "Table", "Systems", options="Privileged Access Scope", reqd=1),
			sb("sb_par_just", "Justification"),
			f("business_justification", "Text", "Business Justification", reqd=1),
			sb("sb_par_approval", "Approval"),
			f("approval_matrix", "Link", "Approval Matrix", options="Approval Matrix"),
			f("approval_status", "Select", "Approval Status", read_only=1, default="Pending",
			  options="Not Required\nPending\nApproved\nRejected"),
			f("current_approval_level", "Int", "Current Level", read_only=1, default="0"),
			f("approvals", "Table", "Approvals", options="Approval History", read_only=1),
			sb("sb_par_grant", "Grant & Revocation"),
			f("granted_by", "Link", "Granted By", options="User", read_only=1),
			f("granted_on", "Datetime", "Granted On", read_only=1),
			cb("cb_par_2"),
			f("revoked_by", "Link", "Revoked By", options="User", read_only=1),
			f("revoked_on", "Datetime", "Revoked On", read_only=1),
			f("revocation_reason", "Small Text", "Revocation Reason"),
			sb("sb_par_audit", "Audit"),
			f("audit_notes", "Text", "Audit Notes"),
		]))

	out.append(doctype(
		"Service Desk Audit Log", autoname="hash", sort_field="creation",
		description="Immutable audit trail. Records cannot be edited or deleted through the UI.",
		permissions=[
			P(R_SYS, read=1, report=1, export=1),
			P(R_MANAGER, read=1, report=1, export=1),
			P(R_CISO, read=1, report=1, export=1),
			P(R_AUDITOR, read=1, report=1, export=1),
		],
		track_changes=0,
		fields=[
			f("timestamp", "Datetime", "Timestamp", read_only=1, in_list_view=1, search_index=1),
			f("reference_doctype", "Link", "Type", options="DocType", read_only=1, in_list_view=1,
			  in_standard_filter=1),
			f("reference_name", "Dynamic Link", "Record", options="reference_doctype", read_only=1,
			  in_list_view=1, search_index=1),
			f("action", "Select", "Action", read_only=1, in_list_view=1, in_standard_filter=1,
			  options=("Created\nModified\nAssigned\nStatus Changed\nApproved\nRejected\nComment\n"
			           "Attachment\nDeleted\nExported\nViewed\nEscalated\nSLA Event\n"
			           "Access Granted\nAccess Revoked\nAPI Call")),
			cb("cb_aud_1"),
			f("user", "Link", "User", options="User", read_only=1, in_list_view=1, in_standard_filter=1),
			f("user_full_name", "Data", "User Name", read_only=1),
			f("ip_address", "Data", "IP Address", read_only=1),
			f("browser", "Small Text", "User Agent", read_only=1),
			sb("sb_aud_detail"),
			f("details", "Code", "Details", options="JSON", read_only=1),
		]))

	out.append(doctype(
		"Service Desk Settings", issingle=1,
		permissions=[full_access(R_SYS), full_access(R_MANAGER), P(R_AUDITOR)],
		fields=[
			sb("sb_set_modules", "Enabled Modules"),
			f("enable_incident_management", "Check", "Incident Management", default="1"),
			f("enable_problem_management", "Check", "Problem Management", default="1"),
			f("enable_change_management", "Check", "Change Management", default="1"),
			cb("cb_set_1"),
			f("enable_privileged_access", "Check", "Privileged Access", default="1"),
			f("enable_knowledge_base", "Check", "Knowledge Base", default="1"),
			f("enable_cmdb", "Check", "CMDB", default="1"),
			sb("sb_set_defaults", "Defaults"),
			f("default_sla_policy", "Link", "Default SLA Policy", options="SLA Policy"),
			f("default_team", "Link", "Default Team", options="Service Desk Team"),
			f("default_priority", "Select", "Default Priority", options=PRIORITIES, default="Medium"),
			cb("cb_set_2"),
			f("auto_assign", "Check", "Auto Assign New Tickets", default="1"),
			f("auto_apply_sla", "Check", "Auto Apply SLA", default="1"),
			f("derive_priority_from_impact_urgency", "Check", "Derive Priority From Impact & Urgency",
			  default="1",
			  description="When on, Priority is computed from the Impact/Urgency matrix on save."),
			sb("sb_set_auto", "Automation"),
			f("auto_close_enabled", "Check", "Auto Close Resolved Tickets", default="1"),
			f("auto_close_after_days", "Int", "Auto Close After (days)", default="3",
			  depends_on="auto_close_enabled"),
			f("reminder_before_breach_percent", "Int", "Send Breach Reminder At (% elapsed)", default="75"),
			cb("cb_set_3"),
			f("auto_create_problem_threshold", "Int", "Auto Create Problem After N Similar Incidents",
			  default="5", description="0 disables automatic problem creation."),
			f("suggest_knowledge_articles", "Check", "Suggest Knowledge Articles", default="1"),
			f("satisfaction_survey", "Check", "Send Satisfaction Survey On Close", default="1"),
			sb("sb_set_notify", "Notifications"),
			f("send_email_notifications", "Check", "Email Notifications", default="1"),
			f("send_system_notifications", "Check", "System Notifications", default="1"),
			cb("cb_set_4"),
			f("notify_on_sla_breach", "Check", "Notify On SLA Breach", default="1"),
			f("notify_watchers", "Check", "Notify Watchers", default="1"),
			sb("sb_set_audit", "Audit"),
			f("enable_audit_log", "Check", "Enable Audit Log", default="1"),
			f("audit_retention_days", "Int", "Audit Retention (days)", default="2555",
			  description="0 keeps audit entries forever. Default is 7 years for ISO 27001 / SOC2."),
		]))

	return out


# ---------------------------------------------------------------------------
# patches for circular references
# ---------------------------------------------------------------------------

PATCHES = [
	("Service Desk Team", f("default_category", "Link", "Default Category", options="IT Service Category"),
	 "escalation_user"),
	("SLA Policy", f("apply_to_category", "Link", "Apply To Category", options="IT Service Category"),
	 "apply_24x7"),
	("Approval Matrix", f("category", "Link", "Category", options="IT Service Category"), "department"),
	("Configuration Item", f("relationships", "Table", "Relationships", options="CI Relationship"),
	 "description"),
	("Problem", f("change_request", "Link", "Change Request", options="Change Request"),
	 "knowledge_article"),
	("Change Request", f("ticket", "Link", "Originating Ticket", options="Service Ticket",
	                     read_only=1), "change_owner"),
	("Incident", f("ticket", "Link", "Originating Ticket", options="Service Ticket", read_only=1),
	 "problem"),
]

CI_RELATIONSHIP = doctype("CI Relationship", istable=1, fields=[
	f("relationship_type", "Select", "Relationship", reqd=1, in_list_view=1, columns=3,
	  options="Depends On\nUsed By\nRuns On\nHosts\nConnected To\nPart Of\nBacked Up By"),
	f("configuration_item", "Link", "Configuration Item", options="Configuration Item", reqd=1,
	  in_list_view=1, columns=4),
	f("notes", "Small Text", "Notes", in_list_view=1, columns=5),
])


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------

def _insert(spec, force=False):
	name = spec["name"]
	if frappe.db.exists("DocType", name):
		if not force:
			print(f"  skip   {name}")
			return
		frappe.delete_doc("DocType", name, force=1, ignore_permissions=True)
	doc = frappe.get_doc(spec)
	doc.insert(ignore_permissions=True)
	print(f"  create {name}")


def _patch(doctype_name, field, insert_after):
	meta_doc = frappe.get_doc("DocType", doctype_name)
	if any(d.fieldname == field["fieldname"] for d in meta_doc.fields):
		print(f"  skip   {doctype_name}.{field['fieldname']}")
		return

	idx = next((i for i, d in enumerate(meta_doc.fields) if d.fieldname == insert_after), None)
	row = meta_doc.append("fields", field)
	if idx is not None:
		meta_doc.fields.remove(row)
		meta_doc.fields.insert(idx + 1, row)
		for i, d in enumerate(meta_doc.fields):
			d.idx = i + 1
	meta_doc.save(ignore_permissions=True)
	print(f"  patch  {doctype_name}.{field['fieldname']}")


def run(force=False):
	from turacoz_service_desk.turacoz_it_service_desk.setup import install

	force = force in (True, "True", "true", 1, "1")
	frappe.flags.in_install = True

	print("== roles & module ==")
	install.before_install()

	groups = [
		("child tables", child_tables_a()),
		("masters", masters()),
		("masters (category dependent)", masters_late()),
		("child tables (master dependent)", child_tables_b()),
		("problem & change", transactions_a()),
		("incident", transactions_b()),
		("ticket child tables", transactions_c()),
		("service ticket", [service_ticket()]),
		("ticket satellites", transactions_d()),
		("cmdb relationship", [CI_RELATIONSHIP]),
	]

	for label, specs in groups:
		print(f"\n== {label} ==")
		for spec in specs:
			_insert(spec, force=force)

	print("\n== circular reference patches ==")
	for doctype_name, field, after in PATCHES:
		_patch(doctype_name, field, after)

	frappe.db.commit()
	print("\nDone.")
