"""Approval engine: matrix resolution, sequential/parallel levels, approve & reject actions."""

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from turacoz_service_desk.turacoz_it_service_desk.engine import utils

PENDING = "Pending"
APPROVED = "Approved"
REJECTED = "Rejected"
SKIPPED = "Skipped"
NOT_REQUIRED = "Not Required"

REQUESTER_FIELDS = ("requester", "requested_by", "owner")


# ---------------------------------------------------------------------------
# matrix resolution
# ---------------------------------------------------------------------------

def resolve_matrix(doc):
	"""Best matching active Approval Matrix for a document, or None."""
	if doc.get("approval_matrix"):
		return doc.approval_matrix

	if doc.doctype == "Service Ticket" and doc.get("service"):
		service = frappe.get_cached_doc("Service Catalog", doc.service)
		if service.approval_required and service.approval_matrix:
			return service.approval_matrix

	matrices = frappe.get_all(
		"Approval Matrix",
		filters={"applies_to": doc.doctype, "is_active": 1},
		fields=["name", "category", "department", "priority", "risk_level",
		        "min_amount", "max_amount"],
	)

	best, best_score = None, -1
	for matrix in matrices:
		score = _match_score(matrix, doc)
		if score is not None and score > best_score:
			best, best_score = matrix.name, score
	return best


def _match_score(matrix, doc):
	"""None when a condition is violated, otherwise the count of matched conditions."""
	score = 0
	categories = [c for c in (doc.get("category"), doc.get("sub_category")) if c]

	if matrix.category:
		if matrix.category not in categories:
			return None
		score += 1
	if matrix.department:
		if matrix.department != doc.get("department"):
			return None
		score += 1
	if matrix.priority:
		if matrix.priority != doc.get("priority"):
			return None
		score += 1
	if matrix.risk_level:
		if matrix.risk_level != doc.get("risk"):
			return None
		score += 1

	amount = flt(doc.get("estimated_cost") or doc.get("amount"))
	if flt(matrix.min_amount) and amount < flt(matrix.min_amount):
		return None
	if flt(matrix.max_amount) and amount > flt(matrix.max_amount):
		return None
	if flt(matrix.min_amount) or flt(matrix.max_amount):
		score += 1
	return score


def is_approval_required(doc):
	if doc.doctype == "Service Ticket":
		if doc.get("service"):
			if frappe.db.get_value("Service Catalog", doc.service, "approval_required"):
				return True
		for fieldname in ("sub_category", "category"):
			category = doc.get(fieldname)
			if category and frappe.db.get_value("IT Service Category", category, "requires_approval"):
				return True
		return bool(doc.get("approval_matrix"))

	if doc.doctype == "Change Request":
		return doc.get("change_type") != "Standard" or bool(doc.get("cab_required"))

	if doc.doctype == "Privileged Access Request":
		return True

	return bool(doc.get("approval_matrix"))


# ---------------------------------------------------------------------------
# approver resolution
# ---------------------------------------------------------------------------

def get_requester(doc):
	for fieldname in REQUESTER_FIELDS:
		value = doc.get(fieldname)
		if value:
			return value
	return doc.owner


def resolve_approver(level, doc):
	"""(user, role) for an Approval Matrix Level. Either may be None."""
	kind = level.approver_type

	if kind == "Specific User":
		return level.approver_user, None
	if kind == "Role":
		return None, level.approver_role
	if kind == "Requester Manager":
		return utils.get_reporting_manager(get_requester(doc)), "Department Head"
	if kind == "Department Head":
		return utils.get_department_head(doc.get("department")), "Department Head"
	if kind == "Team Lead":
		team = doc.get("assigned_team")
		lead = frappe.db.get_value("Service Desk Team", team, "team_lead") if team else None
		return lead, "Service Desk Team Lead"
	if kind == "IT Manager":
		return None, "IT Manager"
	if kind == "CISO":
		return None, "CISO"
	return None, None


def _level_applies(level, doc):
	if not level.condition:
		return True
	try:
		return bool(frappe.safe_eval(level.condition, None, {"doc": doc.as_dict()}))
	except Exception:
		frappe.log_error(frappe.get_traceback(),
		                 f"Approval condition failed on {doc.doctype} {doc.name}")
		return True


# ---------------------------------------------------------------------------
# lifecycle
# ---------------------------------------------------------------------------

def start(doc, matrix=None):
	"""Build the approval trail. Safe to call from validate() - it only writes fields."""
	matrix = matrix or resolve_matrix(doc)
	if not matrix:
		doc.approval_status = NOT_REQUIRED
		return False

	matrix_doc = frappe.get_cached_doc("Approval Matrix", matrix)
	doc.approval_matrix = matrix
	doc.set("approvals", [])

	levels = sorted(matrix_doc.levels, key=lambda level: cint(level.level))
	added = 0
	for level in levels:
		user, role = resolve_approver(level, doc)
		if not _level_applies(level, doc):
			doc.append("approvals", {
				"approval_level": cint(level.level),
				"approver": user,
				"approver_role": role,
				"status": SKIPPED,
				"action_on": now_datetime(),
				"comments": "Condition not met",
			})
			continue
		if not user and not role:
			if level.is_mandatory:
				frappe.throw(_("No approver could be resolved for approval level {0}.")
				             .format(level.level))
			continue
		doc.append("approvals", {
			"approval_level": cint(level.level),
			"approver": user,
			"approver_role": role,
			"status": PENDING,
		})
		added += 1

	if not added:
		doc.approval_status = NOT_REQUIRED
		return False

	doc.approval_status = PENDING
	doc.current_approval_level = min(
		(row.approval_level for row in doc.approvals if row.status == PENDING),
		default=0,
	)
	utils.add_timeline(doc, "Approval", f"Approval started using {matrix}")
	return True


def pending_rows(doc, level=None):
	rows = [row for row in doc.get("approvals", []) if row.status == PENDING]
	if level is not None:
		rows = [row for row in rows if cint(row.approval_level) == cint(level)]
	return rows


def can_action(row, user=None):
	user = user or frappe.session.user
	if row.approver and row.approver == user:
		return True
	if row.approver_role and row.approver_role in frappe.get_roles(user):
		return True
	return user == "Administrator"


def actionable_rows(doc, user=None):
	"""Rows the user may act on right now, honouring sequential ordering."""
	matrix_mode = frappe.db.get_value("Approval Matrix", doc.get("approval_matrix"),
	                                  "approval_mode") or "Sequential"
	rows = pending_rows(doc)
	if matrix_mode == "Sequential" and rows:
		current = min(cint(row.approval_level) for row in rows)
		rows = [row for row in rows if cint(row.approval_level) == current]
	return [row for row in rows if can_action(row, user)]


@frappe.whitelist()
def get_approval_state(doctype, name, user=None):
	"""Used by the form to decide whether to show the approve / reject buttons."""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	if doc.get("approval_status") != PENDING:
		return {"can_action": False, "level": 0}
	rows = actionable_rows(doc, user)
	return {
		"can_action": bool(rows),
		"level": cint(doc.get("current_approval_level")),
		"pending_with": [row.approver or row.approver_role for row in pending_rows(doc)],
	}


@frappe.whitelist()
def approve(doctype, name, comments=None):
	return _action(doctype, name, APPROVED, comments)


@frappe.whitelist()
def reject(doctype, name, comments=None):
	if not comments:
		frappe.throw(_("A reason is required to reject."))
	return _action(doctype, name, REJECTED, comments)


def _action(doctype, name, status, comments):
	from turacoz_service_desk.turacoz_it_service_desk.engine import audit, notification

	doc = frappe.get_doc(doctype, name)
	rows = actionable_rows(doc)
	if not rows:
		frappe.throw(_("You are not a pending approver for {0}.").format(name))

	for row in rows:
		row.status = status
		row.approver = row.approver or frappe.session.user
		row.action_on = now_datetime()
		row.comments = comments

	if status == REJECTED:
		doc.approval_status = REJECTED
		for row in pending_rows(doc):
			row.status = SKIPPED
			row.comments = "Rejected at an earlier level"
	else:
		remaining = pending_rows(doc)
		doc.approval_status = PENDING if remaining else APPROVED
		doc.current_approval_level = min(
			(cint(row.approval_level) for row in remaining), default=0
		)

	utils.add_timeline(doc, "Approval", f"{status} by {frappe.session.user}",
	                   to_value=comments)
	doc.flags.approval_action = status
	doc.save(ignore_permissions=True)

	audit.log(doctype, name, status, {"comments": comments})
	notification.notify(doc, "approval_" + status.lower())
	if doc.approval_status == PENDING:
		notification.notify(doc, "approval_pending")
	frappe.db.commit()
	return {"name": doc.name, "approval_status": doc.approval_status,
	        "current_approval_level": doc.current_approval_level}


@frappe.whitelist()
def get_pending_approvals(user=None):
	"""Everything waiting on this user across the service desk doctypes."""
	user = user or frappe.session.user
	roles = frappe.get_roles(user)
	out = []
	for doctype in ("Service Ticket", "Change Request", "Privileged Access Request"):
		rows = frappe.get_all(
			"Approval History",
			filters={"parenttype": doctype, "status": PENDING},
			fields=["parent", "approval_level", "approver", "approver_role"],
		)
		for row in rows:
			if row.approver == user or (row.approver_role and row.approver_role in roles):
				parent = frappe.db.get_value(
					doctype, row.parent,
					["name", "approval_status", "current_approval_level", "modified"],
					as_dict=True,
				)
				if not parent or parent.approval_status != PENDING:
					continue
				if cint(parent.current_approval_level) != cint(row.approval_level):
					continue
				out.append({
					"doctype": doctype,
					"name": row.parent,
					"level": row.approval_level,
					"modified": parent.modified,
				})
	return sorted(out, key=lambda d: d["modified"], reverse=True)
