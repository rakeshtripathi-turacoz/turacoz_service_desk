"""Assignment engine: team routing plus round robin, load balancing and skill based picking."""

import frappe
from frappe.utils import cint, now_datetime

from turacoz_service_desk.turacoz_it_service_desk.engine import utils

OPEN_FILTER = ["not in", ("Resolved", "Closed", "Cancelled")]


# ---------------------------------------------------------------------------
# team routing
# ---------------------------------------------------------------------------

def resolve_team(doc):
	if doc.get("assigned_team"):
		return doc.assigned_team

	for fieldname in ("sub_category", "category"):
		category = doc.get(fieldname)
		if not category:
			continue
		team = frappe.db.get_value("IT Service Category", category, "default_team")
		if team and frappe.db.get_value("Service Desk Team", team, "is_active"):
			return team
		team = frappe.db.get_value(
			"Service Desk Team", {"default_category": category, "is_active": 1}, "name"
		)
		if team:
			return team

	team = utils.setting("default_team")
	if team and frappe.db.get_value("Service Desk Team", team, "is_active"):
		return team
	return None


def resolve_engineer(doc, team):
	"""Pick an engineer for a ticket using the team's assignment method."""
	if not team:
		return None

	team_doc = frappe.get_cached_doc("Service Desk Team", team)
	candidates = [
		m.user for m in team_doc.members
		if m.is_available and utils.user_exists(m.user)
	]
	if not candidates:
		return None

	# a category level default engineer always wins when they are on the team
	for fieldname in ("sub_category", "category"):
		category = doc.get(fieldname)
		if not category:
			continue
		preferred = frappe.db.get_value("IT Service Category", category, "default_engineer")
		if preferred and preferred in candidates:
			return preferred

	method = team_doc.assignment_method or "Round Robin"
	if method == "Manual":
		return None
	if method == "Load Balancing":
		return _by_load(team_doc, candidates)
	if method == "Skill Based":
		return _by_skill(doc, team_doc, candidates) or _by_load(team_doc, candidates)
	return _round_robin(team_doc, candidates)


def _open_counts(users):
	counts = dict.fromkeys(users, 0)
	rows = frappe.get_all(
		"Service Ticket",
		filters={"assigned_engineer": ["in", users], "status": OPEN_FILTER},
		fields=["assigned_engineer", "count(name) as total"],
		group_by="assigned_engineer",
	)
	for row in rows:
		counts[row.assigned_engineer] = cint(row.total)
	return counts


def _capacity(team_doc, user):
	for member in team_doc.members:
		if member.user == user:
			return cint(member.max_open_tickets)
	return 0


def _by_load(team_doc, candidates):
	counts = _open_counts(candidates)
	available = [
		u for u in candidates
		if not _capacity(team_doc, u) or counts[u] < _capacity(team_doc, u)
	]
	pool = available or candidates
	return min(pool, key=lambda u: (counts[u], u))


def _round_robin(team_doc, candidates):
	last = frappe.get_all(
		"Service Ticket",
		filters={"assigned_team": team_doc.name, "assigned_engineer": ["in", candidates]},
		fields=["assigned_engineer"],
		order_by="creation desc",
		limit=1,
	)
	if not last:
		return candidates[0]
	try:
		idx = candidates.index(last[0].assigned_engineer)
	except ValueError:
		return candidates[0]
	return candidates[(idx + 1) % len(candidates)]


SKILL_WEIGHT = {"Expert": 0, "Intermediate": 1, "Beginner": 2}


def _by_skill(doc, team_doc, candidates):
	categories = [c for c in (doc.get("sub_category"), doc.get("category")) if c]
	if not categories:
		return None

	skills = frappe.get_all(
		"Engineer Skill",
		filters={"engineer": ["in", candidates], "category": ["in", categories], "is_active": 1},
		fields=["engineer", "skill_level", "is_certified", "category"],
	)
	if not skills:
		return None

	counts = _open_counts(candidates)
	best = sorted(
		skills,
		key=lambda s: (
			0 if s.category == doc.get("sub_category") else 1,
			SKILL_WEIGHT.get(s.skill_level, 3),
			0 if s.is_certified else 1,
			counts.get(s.engineer, 0),
			s.engineer,
		),
	)
	for skill in best:
		capacity = _capacity(team_doc, skill.engineer)
		if not capacity or counts.get(skill.engineer, 0) < capacity:
			return skill.engineer
	return best[0].engineer


# ---------------------------------------------------------------------------
# applying the assignment
# ---------------------------------------------------------------------------

def auto_assign(doc, reason="Auto assignment"):
	"""Fill assigned_team / assigned_engineer in place. Safe to call from validate()."""
	if not utils.setting("auto_assign", 1):
		return

	team = resolve_team(doc)
	if team and team != doc.get("assigned_team"):
		doc.assigned_team = team
	if doc.get("assigned_engineer"):
		return

	engineer = resolve_engineer(doc, doc.get("assigned_team"))
	if engineer:
		doc.assigned_engineer = engineer
		record_history(doc, engineer, reason)
		if doc.status in ("Draft", "Open"):
			doc.status = "Assigned"


def record_history(doc, engineer, reason=None):
	if not doc.meta.has_field("assignment_history"):
		return
	doc.append("assignment_history", {
		"assigned_to": engineer,
		"team": doc.get("assigned_team"),
		"assigned_by": frappe.session.user,
		"assigned_on": now_datetime(),
		"reason": (reason or "")[:140],
	})


def sync_todo(doc, previous_engineer=None):
	"""Mirror the assignment into Frappe's ToDo/_assign so it shows in the sidebar."""
	from frappe.desk.form.assign_to import add as assign_add, remove as assign_remove

	engineer = doc.get("assigned_engineer")
	if previous_engineer and previous_engineer != engineer:
		try:
			assign_remove(doc.doctype, doc.name, previous_engineer)
		except Exception:
			pass

	if not engineer or engineer == previous_engineer:
		return

	try:
		assign_add({
			"doctype": doc.doctype,
			"name": doc.name,
			"assign_to": [engineer],
			"description": doc.get("subject") or doc.name,
			"priority": _todo_priority(doc.get("priority")),
			"notify": 0,
		})
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Could not create ToDo for {doc.name}")


def _todo_priority(priority):
	return {"Critical": "High", "High": "High", "Medium": "Medium", "Low": "Low"}.get(
		priority, "Medium"
	)


@frappe.whitelist()
def reassign(ticket, engineer=None, team=None, reason=None):
	"""Manual (re)assignment from the ticket form or the REST API."""
	doc = frappe.get_doc("Service Ticket", ticket)
	doc.check_permission("write")

	previous = doc.assigned_engineer
	if team:
		doc.assigned_team = team
	if engineer:
		doc.assigned_engineer = engineer
	elif team:
		doc.assigned_engineer = resolve_engineer(doc, team)

	if not doc.assigned_engineer:
		frappe.throw(frappe._("No engineer could be determined for this ticket."))

	record_history(doc, doc.assigned_engineer, reason or "Manual reassignment")
	utils.add_timeline(doc, "Assignment", reason or "Reassigned",
	                   previous, doc.assigned_engineer)
	if doc.status in ("Draft", "Open"):
		doc.status = "Assigned"
	doc.save()
	frappe.db.commit()
	return {"ticket": doc.name, "assigned_engineer": doc.assigned_engineer,
	        "assigned_team": doc.assigned_team}


@frappe.whitelist()
def get_workload(team=None):
	"""Open ticket count per engineer, for the manager dashboard."""
	filters = {"status": OPEN_FILTER, "assigned_engineer": ["is", "set"]}
	if team:
		filters["assigned_team"] = team
	return frappe.get_all(
		"Service Ticket",
		filters=filters,
		fields=["assigned_engineer", "count(name) as open_tickets"],
		group_by="assigned_engineer",
		order_by="open_tickets desc",
	)
