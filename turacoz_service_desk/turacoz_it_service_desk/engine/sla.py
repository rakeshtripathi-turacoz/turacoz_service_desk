"""SLA engine: policy resolution, working-hour deadlines, pause/resume, breach and escalation.

All deadline arithmetic happens in *working* time - the configured business hours of
the policy minus holidays - unless the policy is marked 24x7.
"""

import datetime

import frappe
from frappe.utils import add_to_date, cint, flt, get_datetime, getdate, now_datetime

from turacoz_service_desk.turacoz_it_service_desk.engine import utils

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

PAUSED = "Paused"
ONGOING = "Ongoing"
FULFILLED = "Fulfilled"
FAILED = "Failed"
RESPONSE_OVERDUE = "Response Overdue"
RESOLUTION_OVERDUE = "Resolution Overdue"
NOT_APPLICABLE = "Not Applicable"

MAX_DAYS_SCANNED = 400


# ---------------------------------------------------------------------------
# policy resolution
# ---------------------------------------------------------------------------

def resolve_policy(doc):
	"""Most specific policy wins: service -> category -> policy category rule -> default."""
	if doc.get("service"):
		policy = frappe.db.get_value("Service Catalog", doc.service, "sla_policy")
		if _is_active(policy):
			return policy

	for fieldname in ("sub_category", "category"):
		category = doc.get(fieldname)
		if not category:
			continue
		policy = frappe.db.get_value("IT Service Category", category, "default_sla_policy")
		if _is_active(policy):
			return policy
		policy = frappe.db.get_value("SLA Policy", {"apply_to_category": category, "is_active": 1}, "name")
		if policy:
			return policy

	policy = utils.setting("default_sla_policy")
	if _is_active(policy):
		return policy

	return frappe.db.get_value("SLA Policy", {"is_default": 1, "is_active": 1}, "name")


def _is_active(policy):
	return bool(policy) and bool(frappe.db.get_value("SLA Policy", policy, "is_active"))


def get_policy_doc(policy):
	return frappe.get_cached_doc("SLA Policy", policy) if policy else None


def get_targets(policy_doc, priority):
	"""(response seconds, resolution seconds) for a priority, or (None, None)."""
	for rule in policy_doc.priority_rules:
		if rule.priority == priority:
			return cint(rule.response_time), cint(rule.resolution_time)
	return None, None


# ---------------------------------------------------------------------------
# working time arithmetic
# ---------------------------------------------------------------------------

def _windows_by_weekday(policy_doc):
	windows = {}
	for row in policy_doc.working_days:
		if row.workday not in WEEKDAYS:
			continue
		windows.setdefault(WEEKDAYS.index(row.workday), []).append(
			(_as_time(row.start_time), _as_time(row.end_time))
		)
	for day in windows:
		windows[day].sort()
	return windows


def _as_time(value):
	if isinstance(value, datetime.timedelta):
		total = int(value.total_seconds())
		return datetime.time(total // 3600 % 24, total % 3600 // 60, total % 60)
	if isinstance(value, datetime.time):
		return value
	if isinstance(value, str):
		parts = [int(p) for p in value.split(":")]
		while len(parts) < 3:
			parts.append(0)
		return datetime.time(*parts[:3])
	return datetime.time(0, 0)


def _is_holiday(policy_doc, date):
	if not policy_doc.holiday_list:
		return False
	return bool(frappe.db.exists(
		"Holiday", {"parent": policy_doc.holiday_list, "holiday_date": date}
	))


def _day_windows(policy_doc, windows, date):
	if _is_holiday(policy_doc, date):
		return []
	return [
		(datetime.datetime.combine(date, start), datetime.datetime.combine(date, end))
		for start, end in windows.get(date.weekday(), [])
		if end > start
	]


def add_working_seconds(policy_doc, start, seconds):
	"""Datetime reached after consuming `seconds` of business time from `start`."""
	start = get_datetime(start)
	seconds = cint(seconds)
	if seconds <= 0:
		return start
	if not policy_doc or policy_doc.apply_24x7:
		return add_to_date(start, seconds=seconds)

	windows = _windows_by_weekday(policy_doc)
	if not windows:
		return add_to_date(start, seconds=seconds)

	remaining = seconds
	date = getdate(start)
	cursor = start
	for _ in range(MAX_DAYS_SCANNED):
		for window_start, window_end in _day_windows(policy_doc, windows, date):
			if cursor >= window_end:
				continue
			effective = max(cursor, window_start)
			available = (window_end - effective).total_seconds()
			if available >= remaining:
				return effective + datetime.timedelta(seconds=remaining)
			remaining -= available
			cursor = window_end
		date = date + datetime.timedelta(days=1)
		cursor = datetime.datetime.combine(date, datetime.time(0, 0))

	# policy has no reachable business hours - fall back to calendar time
	return add_to_date(start, seconds=seconds)


def working_seconds_between(policy_doc, start, end):
	"""Business seconds elapsed between two datetimes."""
	start, end = get_datetime(start), get_datetime(end)
	if end <= start:
		return 0
	if not policy_doc or policy_doc.apply_24x7:
		return (end - start).total_seconds()

	windows = _windows_by_weekday(policy_doc)
	if not windows:
		return (end - start).total_seconds()

	total = 0
	date = getdate(start)
	last_date = getdate(end)
	while date <= last_date:
		for window_start, window_end in _day_windows(policy_doc, windows, date):
			overlap_start = max(window_start, start)
			overlap_end = min(window_end, end)
			if overlap_end > overlap_start:
				total += (overlap_end - overlap_start).total_seconds()
		date = date + datetime.timedelta(days=1)
	return total


# ---------------------------------------------------------------------------
# applying the SLA to a ticket
# ---------------------------------------------------------------------------

def apply(doc, force=False):
	"""Set policy and deadlines on a Service Ticket."""
	if doc.status == "Cancelled":
		doc.sla_status = NOT_APPLICABLE
		return

	if not utils.setting("auto_apply_sla", 1) and not force:
		return

	policy = doc.sla_policy if (doc.sla_policy and not force) else resolve_policy(doc)
	if not policy:
		doc.sla_status = NOT_APPLICABLE
		return

	policy_doc = get_policy_doc(policy)
	response_seconds, resolution_seconds = get_targets(policy_doc, doc.priority)
	if response_seconds is None:
		doc.sla_status = NOT_APPLICABLE
		return

	start = get_datetime(doc.opened_on or doc.creation or now_datetime())
	doc.sla_policy = policy
	doc.response_by = add_working_seconds(policy_doc, start, response_seconds)
	doc.resolution_by = add_working_seconds(policy_doc, start, resolution_seconds)
	if doc.total_hold_time:
		doc.response_by = add_working_seconds(policy_doc, doc.response_by, doc.total_hold_time)
		doc.resolution_by = add_working_seconds(policy_doc, doc.resolution_by, doc.total_hold_time)
	if not doc.sla_status or doc.sla_status == NOT_APPLICABLE:
		doc.sla_status = ONGOING

	log_event(doc, "SLA Applied", f"{policy} | priority {doc.priority}")


def is_paused_status(policy_doc, status):
	return any(row.status == status for row in (policy_doc.pause_statuses if policy_doc else []))


def handle_status_change(doc, previous_status):
	"""Pause/resume the clock and stamp response, resolution and closure milestones."""
	policy_doc = get_policy_doc(doc.sla_policy)
	if not policy_doc:
		return

	now = now_datetime()

	was_paused = is_paused_status(policy_doc, previous_status)
	is_paused = is_paused_status(policy_doc, doc.status)

	if is_paused and not was_paused:
		doc.hold_started_on = now
		doc.sla_status = PAUSED
		log_event(doc, "Paused", f"Status moved to {doc.status}")
	elif was_paused and not is_paused:
		held = working_seconds_between(policy_doc, doc.hold_started_on or now, now)
		doc.total_hold_time = flt(doc.total_hold_time) + held
		if doc.response_by and not doc.first_responded_on:
			doc.response_by = add_working_seconds(policy_doc, doc.response_by, held)
		if doc.resolution_by:
			doc.resolution_by = add_working_seconds(policy_doc, doc.resolution_by, held)
		doc.hold_started_on = None
		doc.sla_status = ONGOING
		log_event(doc, "Resumed", f"Held for {int(held / 60)} minutes")

	if doc.status in ("Resolved", "Closed") and previous_status not in ("Resolved", "Closed"):
		mark_resolved(doc, now)

	if doc.status == "Reopened" and previous_status in ("Resolved", "Closed", "User Verification"):
		reset_for_reopen(doc)


def note_first_response(doc, when=None):
	"""Called the first time an engineer responds (comment, work log or status move)."""
	if doc.first_responded_on:
		return
	when = get_datetime(when or now_datetime())
	doc.first_responded_on = when
	if doc.response_by:
		met = when <= get_datetime(doc.response_by)
		doc.response_sla_met = 1 if met else 0
		log_event(doc, "Response Met" if met else "Response Breached", f"Responded at {when}")
	else:
		doc.response_sla_met = 1


def mark_resolved(doc, when=None):
	when = get_datetime(when or now_datetime())
	doc.resolved_on = doc.resolved_on or when
	if not doc.first_responded_on:
		note_first_response(doc, when)
	if doc.resolution_by:
		met = get_datetime(doc.resolved_on) <= get_datetime(doc.resolution_by)
		doc.resolution_sla_met = 1 if met else 0
		log_event(doc, "Resolution Met" if met else "Resolution Breached",
		          f"Resolved at {doc.resolved_on}")
	else:
		doc.resolution_sla_met = 1

	if doc.sla_status not in (NOT_APPLICABLE,):
		doc.sla_status = FULFILLED if (doc.response_sla_met and doc.resolution_sla_met) else FAILED


def reset_for_reopen(doc):
	"""A reopened ticket gets a fresh resolution window."""
	policy_doc = get_policy_doc(doc.sla_policy)
	if not policy_doc:
		return
	_, resolution_seconds = get_targets(policy_doc, doc.priority)
	if resolution_seconds is None:
		return
	start = now_datetime()
	doc.resolution_by = add_working_seconds(policy_doc, start, resolution_seconds)
	doc.resolution_sla_met = 0
	doc.resolved_on = None
	doc.sla_status = ONGOING
	log_event(doc, "Reset", "Ticket reopened, resolution clock restarted")


def log_event(doc, event, details=None):
	if not doc.meta.has_field("sla_events"):
		return
	doc.append("sla_events", {
		"event": event,
		"event_time": now_datetime(),
		"details": (details or "")[:500],
	})


# ---------------------------------------------------------------------------
# breach detection and escalation (scheduled)
# ---------------------------------------------------------------------------

def percent_elapsed(policy_doc, start, deadline, now=None):
	now = get_datetime(now or now_datetime())
	start, deadline = get_datetime(start), get_datetime(deadline)
	total = working_seconds_between(policy_doc, start, deadline)
	if total <= 0:
		return 100.0 if now >= deadline else 0.0
	used = working_seconds_between(policy_doc, start, now)
	return min(used / total * 100.0, 999.0)


def check_breaches():
	"""Scheduled: flag overdue tickets and run escalation rules. Runs every 15 minutes."""
	tickets = frappe.get_all(
		"Service Ticket",
		filters={
			"status": ["not in", ("Resolved", "Closed", "Cancelled")],
			"sla_status": ["in", (ONGOING, RESPONSE_OVERDUE, RESOLUTION_OVERDUE)],
			"sla_policy": ["is", "set"],
		},
		pluck="name",
		limit_page_length=0,
	)
	for name in tickets:
		try:
			evaluate_ticket(name)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"SLA check failed for {name}")
	frappe.db.commit()


def evaluate_ticket(name):
	from turacoz_service_desk.turacoz_it_service_desk.engine import notification

	doc = frappe.get_doc("Service Ticket", name)
	policy_doc = get_policy_doc(doc.sla_policy)
	if not policy_doc:
		return

	now = now_datetime()
	start = get_datetime(doc.opened_on or doc.creation)
	dirty = False

	response_pct = (
		percent_elapsed(policy_doc, start, doc.response_by, now)
		if doc.response_by and not doc.first_responded_on else None
	)
	resolution_pct = (
		percent_elapsed(policy_doc, start, doc.resolution_by, now) if doc.resolution_by else None
	)

	if response_pct is not None and now > get_datetime(doc.response_by) and \
			doc.sla_status != RESPONSE_OVERDUE:
		doc.sla_status = RESPONSE_OVERDUE
		doc.response_sla_met = 0
		log_event(doc, "Response Breached", "First response deadline passed")
		notification.notify(doc, "sla_breach", extra={"breach": "response"})
		dirty = True

	if resolution_pct is not None and now > get_datetime(doc.resolution_by) and \
			doc.sla_status != RESOLUTION_OVERDUE:
		doc.sla_status = RESOLUTION_OVERDUE
		doc.resolution_sla_met = 0
		log_event(doc, "Resolution Breached", "Resolution deadline passed")
		notification.notify(doc, "sla_breach", extra={"breach": "resolution"})
		dirty = True

	applied = {e.details for e in doc.sla_events if e.event == "Escalated"}
	for idx, rule in enumerate(policy_doc.escalation_rules, start=1):
		pct = response_pct if rule.escalation_type == "Response" else resolution_pct
		if pct is None or pct < flt(rule.after_percent):
			continue
		tag = f"rule:{idx}"
		if any(tag in (detail or "") for detail in applied):
			continue
		_escalate(doc, rule, tag, pct)
		dirty = True

	if dirty:
		doc.flags.ignore_validate_update_after_submit = True
		doc.save(ignore_permissions=True)


def _escalate(doc, rule, tag, pct):
	from turacoz_service_desk.turacoz_it_service_desk.engine import notification

	recipients = []
	if rule.escalate_to_user:
		recipients.append(rule.escalate_to_user)
	if rule.escalate_to_role:
		recipients.extend(utils.get_users_with_role(rule.escalate_to_role))

	doc.is_escalated = 1
	doc.escalation_level = cint(doc.escalation_level) + 1

	if rule.increase_priority:
		new_priority = utils.raise_priority(doc.priority)
		if new_priority != doc.priority:
			utils.add_timeline(doc, "Escalation", "Priority raised by escalation rule",
			                   doc.priority, new_priority)
			doc.priority = new_priority

	log_event(doc, "Escalated",
	          f"{tag} | {rule.escalation_type} at {pct:.0f}% -> "
	          f"{rule.escalate_to_user or rule.escalate_to_role}")
	utils.add_timeline(doc, "Escalation",
	                   f"Escalated ({rule.escalation_type} {rule.after_percent}%)")

	if recipients:
		notification.notify(doc, "escalation", recipients=list(set(recipients)))
	if rule.notify_requester and doc.requester:
		notification.notify(doc, "escalation", recipients=[doc.requester])


def send_breach_reminders():
	"""Scheduled: warn owners before the resolution deadline is consumed."""
	from turacoz_service_desk.turacoz_it_service_desk.engine import notification

	threshold = cint(utils.setting("reminder_before_breach_percent", 75)) or 75
	tickets = frappe.get_all(
		"Service Ticket",
		filters={
			"status": ["not in", ("Resolved", "Closed", "Cancelled")],
			"sla_status": ONGOING,
			"resolution_by": ["is", "set"],
		},
		fields=["name", "sla_policy", "opened_on", "creation", "resolution_by",
		        "assigned_engineer", "assigned_team"],
		limit_page_length=0,
	)
	for row in tickets:
		policy_doc = get_policy_doc(row.sla_policy)
		if not policy_doc:
			continue
		pct = percent_elapsed(policy_doc, row.opened_on or row.creation, row.resolution_by)
		if pct < threshold or pct >= 100:
			continue
		if frappe.db.exists("SLA Event", {
			"parent": row.name, "event": "Escalated", "details": ["like", "%reminder%"]
		}):
			continue
		doc = frappe.get_doc("Service Ticket", row.name)
		log_event(doc, "Escalated", f"reminder sent at {pct:.0f}%")
		doc.save(ignore_permissions=True)
		notification.notify(doc, "sla_reminder", extra={"percent": round(pct)})
	frappe.db.commit()


@frappe.whitelist()
def get_sla_status(ticket):
	"""Live SLA countdown for a ticket. Used by the form dashboard and the REST API."""
	doc = frappe.get_doc("Service Ticket", ticket)
	doc.check_permission("read")
	policy_doc = get_policy_doc(doc.sla_policy)
	now = now_datetime()
	start = get_datetime(doc.opened_on or doc.creation)

	def remaining(deadline):
		if not deadline or not policy_doc:
			return None
		deadline = get_datetime(deadline)
		if deadline <= now:
			return -working_seconds_between(policy_doc, deadline, now)
		return working_seconds_between(policy_doc, now, deadline)

	return {
		"ticket": doc.name,
		"policy": doc.sla_policy,
		"status": doc.sla_status,
		"response_by": doc.response_by,
		"resolution_by": doc.resolution_by,
		"first_responded_on": doc.first_responded_on,
		"response_remaining_seconds": remaining(doc.response_by) if not doc.first_responded_on else 0,
		"resolution_remaining_seconds": remaining(doc.resolution_by),
		"response_percent": (
			percent_elapsed(policy_doc, start, doc.response_by, now)
			if policy_doc and doc.response_by and not doc.first_responded_on else 100
		),
		"resolution_percent": (
			percent_elapsed(policy_doc, start, doc.resolution_by, now)
			if policy_doc and doc.resolution_by else 0
		),
		"total_hold_time": doc.total_hold_time,
		"is_escalated": doc.is_escalated,
		"escalation_level": doc.escalation_level,
	}
