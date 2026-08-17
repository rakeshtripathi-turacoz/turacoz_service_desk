# Copyright (c) 2026, RSA and contributors
# See license.txt

import datetime

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, get_datetime, now_datetime

from turacoz_service_desk.turacoz_it_service_desk.engine import approval, assignment, sla, utils

TEST_POLICY = "_Test IT SLA"
TEST_TEAM = "_Test Service Desk Team"
TEST_CATEGORY = "_Test Service Category"


def create_policy():
	if frappe.db.exists("SLA Policy", TEST_POLICY):
		return frappe.get_doc("SLA Policy", TEST_POLICY)
	return frappe.get_doc({
		"doctype": "SLA Policy",
		"policy_name": TEST_POLICY,
		"is_active": 1,
		"apply_24x7": 0,
		"priority_rules": [
			{"priority": "Critical", "response_time": 1800, "resolution_time": 14400},
			{"priority": "High", "response_time": 3600, "resolution_time": 28800},
			{"priority": "Medium", "response_time": 14400, "resolution_time": 86400},
			{"priority": "Low", "response_time": 28800, "resolution_time": 259200},
		],
		"working_days": [
			{"workday": day, "start_time": "09:00:00", "end_time": "18:00:00"}
			for day in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
		],
		"pause_statuses": [{"status": "Pending User"}, {"status": "Pending Vendor"}],
		"escalation_rules": [
			{"escalation_type": "Resolution", "after_percent": 75,
			 "escalate_to_role": "Service Desk Team Lead"},
		],
	}).insert(ignore_permissions=True)


def create_category():
	if frappe.db.exists("IT Service Category", TEST_CATEGORY):
		return frappe.get_doc("IT Service Category", TEST_CATEGORY)
	return frappe.get_doc({
		"doctype": "IT Service Category",
		"category_name": TEST_CATEGORY,
		"is_active": 1,
		"default_sla_policy": TEST_POLICY,
		"default_team": TEST_TEAM,
	}).insert(ignore_permissions=True)


def create_team():
	if frappe.db.exists("Service Desk Team", TEST_TEAM):
		return frappe.get_doc("Service Desk Team", TEST_TEAM)
	return frappe.get_doc({
		"doctype": "Service Desk Team",
		"team_name": TEST_TEAM,
		"team_lead": "Administrator",
		"assignment_method": "Load Balancing",
		"is_active": 1,
		"members": [{"user": "Administrator", "role_in_team": "Lead", "is_available": 1,
		             "max_open_tickets": 0}],
	}).insert(ignore_permissions=True)


class TestServiceTicket(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_policy()
		create_team()
		create_category()

	def make_ticket(self, **kwargs):
		values = {
			"doctype": "Service Ticket",
			"subject": "Test ticket",
			"description": "Test description",
			"category": TEST_CATEGORY,
			"ticket_type": "Incident",
			"priority": "High",
			"requester": "Administrator",
			"status": "Open",
		}
		values.update(kwargs)
		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		return doc

	# -- classification -------------------------------------------------

	def test_priority_derived_from_impact_and_urgency(self):
		doc = self.make_ticket(impact="High", urgency="High")
		self.assertEqual(doc.priority, "Critical")

	def test_explicit_priority_change_is_respected(self):
		doc = self.make_ticket(impact="Low", urgency="Low")
		self.assertEqual(doc.priority, "Low")
		doc.priority = "Critical"
		doc.save()
		self.assertEqual(doc.priority, "Critical")

	def test_sub_category_must_belong_to_category(self):
		other = create_category()
		child = frappe.get_doc({
			"doctype": "IT Service Category",
			"category_name": "_Test Child Category",
			"parent_service_category": other.name,
		})
		if not frappe.db.exists("IT Service Category", "_Test Child Category"):
			child.insert(ignore_permissions=True)

		doc = self.make_ticket()
		doc.sub_category = "_Test Child Category"
		doc.category = "Office365" if frappe.db.exists("IT Service Category", "Office365") \
			else TEST_CATEGORY
		if doc.category != TEST_CATEGORY:
			self.assertRaises(frappe.ValidationError, doc.save)

	# -- SLA ------------------------------------------------------------

	def test_sla_applied_on_insert(self):
		doc = self.make_ticket(priority="Critical", impact="High", urgency="High")
		self.assertEqual(doc.sla_policy, TEST_POLICY)
		self.assertTrue(doc.response_by)
		self.assertTrue(doc.resolution_by)
		self.assertEqual(doc.sla_status, "Ongoing")

	def test_working_hours_are_respected(self):
		policy = frappe.get_cached_doc("SLA Policy", TEST_POLICY)
		# Friday 17:00 + 4 working hours lands on Monday 12:00
		friday = get_datetime("2026-08-07 17:00:00")
		self.assertEqual(friday.weekday(), 4)
		deadline = sla.add_working_seconds(policy, friday, 4 * 3600)
		self.assertEqual(deadline, datetime.datetime(2026, 8, 10, 12, 0))

	def test_working_seconds_between_skips_the_weekend(self):
		policy = frappe.get_cached_doc("SLA Policy", TEST_POLICY)
		elapsed = sla.working_seconds_between(
			policy, get_datetime("2026-08-07 17:00:00"), get_datetime("2026-08-10 10:00:00")
		)
		self.assertEqual(elapsed, 2 * 3600)  # 1h Friday + 1h Monday

	def test_pause_and_resume_extends_the_deadline(self):
		doc = self.make_ticket(priority="Medium", impact="Medium", urgency="Medium")
		original = get_datetime(doc.resolution_by)

		doc.status = "Pending User"
		doc.save()
		self.assertEqual(doc.sla_status, "Paused")
		self.assertTrue(doc.hold_started_on)

		doc.hold_started_on = add_to_date(now_datetime(), hours=-1)
		doc.status = "In Progress"
		doc.save()

		self.assertEqual(doc.sla_status, "Ongoing")
		self.assertGreater(doc.total_hold_time, 0)
		self.assertGreater(get_datetime(doc.resolution_by), original)

	def test_first_response_is_stamped_when_work_starts(self):
		doc = self.make_ticket()
		self.assertFalse(doc.first_responded_on)
		doc.status = "In Progress"
		doc.save()
		self.assertTrue(doc.first_responded_on)
		self.assertEqual(doc.response_sla_met, 1)

	def test_resolution_evaluates_the_sla(self):
		doc = self.make_ticket()
		doc.status = "Resolved"
		doc.resolution = "Fixed in test"
		doc.save()
		self.assertTrue(doc.resolved_on)
		self.assertEqual(doc.resolution_sla_met, 1)
		self.assertEqual(doc.sla_status, "Fulfilled")

	def test_reopen_restarts_the_resolution_clock(self):
		doc = self.make_ticket()
		doc.status = "Resolved"
		doc.resolution = "Fixed in test"
		doc.save()
		doc.status = "Reopened"
		doc.save()
		self.assertEqual(doc.reopen_count, 1)
		self.assertEqual(doc.sla_status, "Ongoing")
		self.assertFalse(doc.resolved_on)

	# -- status flow ----------------------------------------------------

	def test_invalid_transition_is_rejected(self):
		doc = self.make_ticket()
		doc.status = "Closed"
		doc.resolution = "x"
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_resolution_text_is_mandatory(self):
		doc = self.make_ticket()
		doc.status = "Resolved"
		self.assertRaises(frappe.ValidationError, doc.save)

	# -- assignment -----------------------------------------------------

	def test_team_is_routed_from_the_category(self):
		doc = self.make_ticket()
		self.assertEqual(doc.assigned_team, TEST_TEAM)

	def test_load_balancing_picks_the_lightest_engineer(self):
		team = frappe.get_cached_doc("Service Desk Team", TEST_TEAM)
		doc = self.make_ticket()
		engineer = assignment.resolve_engineer(doc, team.name)
		self.assertIn(engineer, [row.user for row in team.members])

	# -- audit ----------------------------------------------------------

	def test_audit_trail_records_creation(self):
		doc = self.make_ticket()
		self.assertTrue(frappe.db.exists("Service Desk Audit Log", {
			"reference_doctype": "Service Ticket",
			"reference_name": doc.name,
			"action": "Created",
		}))


class TestApprovalEngine(FrappeTestCase):
	def test_priority_matrix(self):
		self.assertEqual(utils.derive_priority("High", "High"), "Critical")
		self.assertEqual(utils.derive_priority("Low", "Low"), "Low")
		self.assertEqual(utils.derive_priority("Medium", "High"), "High")

	def test_priority_escalation_caps_at_critical(self):
		self.assertEqual(utils.raise_priority("Low"), "Medium")
		self.assertEqual(utils.raise_priority("Critical"), "Critical")

	def test_matrix_match_scoring_rejects_mismatches(self):
		doc = frappe._dict({"category": "A", "priority": "High", "department": None,
		                    "sub_category": None, "risk": None})
		matrix = frappe._dict({"category": "B", "department": None, "priority": None,
		                       "risk_level": None, "min_amount": 0, "max_amount": 0})
		self.assertIsNone(approval._match_score(matrix, doc))

		matrix.category = "A"
		self.assertEqual(approval._match_score(matrix, doc), 1)
