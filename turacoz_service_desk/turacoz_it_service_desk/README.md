# Turacoz IT Service Desk (TSD)

Enterprise ITSM module for ERPNext 15 / Frappe 15, implemented as a module inside the
`tms` app (`tms/turacoz_it_service_desk`). It follows the ITIL practices set out in the
product requirements: incidents, service requests, problems, changes, privileged access,
CMDB, knowledge base, SLA, approvals, notifications and an immutable audit trail.

---

## 1. Layout

```
turacoz_it_service_desk/
├── _build_doctypes.py      one-shot schema builder (JSON under doctype/ is the source of truth)
├── api/                    REST endpoints  (response.py, ticket.py, itsm.py, dashboard.py)
├── doctype/                36 DocTypes with their controllers, JS and tests
├── engine/                 business logic  (sla, assignment, approval, notification,
│                                            audit, automation, knowledge, utils)
├── report/                 12 script reports
└── setup/                  install.py (roles + master data), desk.py (reports, cards,
                            charts, workspace), demo.py (UAT data)
```

The employee portal lives at `tms/www/support/` and is served at **`/support`**.

---

## 2. Bootstrapping a site

```bash
# 1. schema (idempotent; pass force=True to rebuild a DocType from scratch)
bench --site <site> execute turacoz_service_desk.turacoz_it_service_desk._build_doctypes.run

# 2. roles, categories, SLA policy, teams, approval matrices, catalog, settings
bench --site <site> execute turacoz_service_desk.turacoz_it_service_desk.setup.install.after_install

# 3. reports, number cards, dashboard charts and the workspace
bench --site <site> execute turacoz_service_desk.turacoz_it_service_desk.setup.desk.run

# 4. optional demo data for UAT (60 tickets + ITIL records), and its purge
bench --site <site> execute turacoz_service_desk.turacoz_it_service_desk.setup.demo.seed
bench --site <site> execute turacoz_service_desk.turacoz_it_service_desk.setup.demo.purge
```

`after_migrate` (registered in `tms/hooks.py`) re-creates the Module Def and the roles on
every migrate, so a fresh clone of the app never loses them.

---

## 3. Data model

| Group | DocTypes |
|---|---|
| Transactions | Service Ticket, Incident, Problem, Change Request, Privileged Access Request, Work Log, Ticket Comment, Ticket Feedback |
| Masters | IT Service Category, Service Catalog, SLA Policy, Approval Matrix, Service Desk Team, Engineer Skill, Configuration Item, Knowledge Article |
| Config / audit | Service Desk Settings (single), Service Desk Audit Log |
| Child tables | Service Desk Team Member, Service Catalog Document, SLA Priority Rule, SLA Working Day, SLA Escalation Rule, SLA Pause Status, SLA Event, Ticket Timeline, Ticket Watcher, Ticket Asset Link, Approval History, Approval Matrix Level, Assignment History, Related Record, Notification Sent, Privileged Access Scope, Change Affected Service, CI Relationship |

> The category master is called **IT Service Category**, not "Service Category" - that name
> is already taken by the existing Turacoz Management System module.

### Ticket status flow

```
Draft → Open → Assigned → In Progress → Pending User / Pending Vendor → Testing
      → Resolved → User Verification → Closed → Reopened
```

Transitions are enforced in `ServiceTicket.validate_status_transition`; anything not in
`ALLOWED_TRANSITIONS` is rejected. `Cancelled` is reachable from every open state.

---

## 4. Engines

### SLA (`engine/sla.py`)
* Policy resolution order: service → sub category → category → category rule on the policy →
  `Service Desk Settings.default_sla_policy` → the policy flagged `is_default`.
* All deadline maths is in **working time**: business hours per weekday, minus the policy's
  holiday list, unless `apply_24x7` is set.
* Pause/resume on configured statuses (default: Pending User, Pending Vendor). Hold time is
  accumulated and both deadlines are pushed forward by the same working duration.
* First response is stamped by the first engineer comment, work log or move into a work
  status. Resolution compliance is evaluated when the ticket reaches Resolved/Closed.
* Reopening restarts the resolution clock (`reset_for_reopen`).
* `check_breaches()` runs every 15 minutes: flags overdue tickets, fires escalation rules
  (`rule:<n>` markers in SLA Events prevent double firing), raises priority and notifies.
* `get_sla_status(ticket)` returns a live countdown - used by the form and the REST API.

### Assignment (`engine/assignment.py`)
Team from category/settings, then engineer by the team's method: **Round Robin**,
**Load Balancing** (respects `max_open_tickets`), **Skill Based** (Engineer Skill, exact
sub-category first, then Expert > Intermediate > Beginner, certification, then load), or
**Manual**. A category-level `default_engineer` always wins when they are on the team.
Assignments are mirrored into Frappe ToDo/`_assign` and recorded in Assignment History.

### Approval (`engine/approval.py`)
Matrix selection scores active matrices on category, department, priority, risk and amount;
the most specific match wins. Levels resolve to Role, Specific User, Department Head,
Team Lead, IT Manager, CISO or Requester Manager (via `Employee.reports_to`), support
Sequential or Parallel mode and an optional python `condition` evaluated with `frappe.safe_eval`.
`approve()` / `reject()` are whitelisted; rejection skips the remaining levels.

### Notification (`engine/notification.py`)
16 templated events (new ticket, assignment, comment, approval, resolution, closure,
SLA breach, escalation, access granted/expiring/revoked, ...) over email and in-app
Notification Log, gated by Service Desk Settings, with watcher support and per-message
delivery logging in the `Notification Sent` table. Failures are logged, never raised.

### Audit (`engine/audit.py`)
`doc_events` on 12 doctypes write an append-only **Service Desk Audit Log** row (user, IP,
user agent, JSON field diff). The controller blocks edits and deletes. Retention is driven by
`audit_retention_days` (default 2555 = 7 years for ISO 27001 / SOC 2).

### Automation (`engine/automation.py`)
| Schedule | Job |
|---|---|
| every 15 min | SLA breach + escalation sweep |
| hourly | pre-breach reminders, privileged access expiry |
| daily | auto close, satisfaction surveys, auto problem creation, expiring-access warnings, audit purge |

### Knowledge (`engine/knowledge.py`)
Token-based article suggestion (title + keywords overlap, category boost, helpful/not-helpful
weighting), free text search, view/helpful counters and one-click article creation from a
resolved ticket.

---

## 5. Roles

`Employee`, `Service Desk Executive`, `Service Desk Engineer`, `Service Desk Team Lead`,
`Department Head`, `IT Manager`, `CISO`, `Auditor`, `System Manager`.

Employees see only tickets they raised, were raised for them, or are assigned to them -
enforced by `get_permission_query_conditions` / `has_permission` on Service Ticket
(registered in `tms/hooks.py`). Auditor is read-only everywhere; the audit log is readable
only by System Manager, IT Manager, CISO and Auditor.

---

## 6. REST API

All endpoints are token authenticated, enforce role permissions and return
`{"success": true, "data": ...}` or `{"success": false, "error": {"code", "message"}}`.

Base: `POST|GET /api/method/turacoz_service_desk.turacoz_it_service_desk.api.<module>.<method>`

**`api.ticket`** — `create`, `update`, `get`, `list_tickets`, `set_status`, `close`,
`reopen`, `add_comment`, `comments`, `add_work_log`, `work_logs`, `submit_feedback`,
`sla_status`, `suggest_articles`, `attachments`

**`api.itsm`** — `create_incident`, `get_incident`, `create_problem`, `create_change`,
`submit_change`, `request_access`, `revoke_access`, `approve`, `reject`,
`pending_approvals`, `search_knowledge`, `get_article`

**`api.dashboard`** — `employee`, `engineer`, `manager`, `executive`, `metrics`

Example:

```bash
curl -X POST https://<site>/api/method/turacoz_service_desk.turacoz_it_service_desk.api.ticket.create \
  -H "Authorization: token <api_key>:<api_secret>" \
  -d subject="VPN is down" -d category="VPN" -d ticket_type="Incident"
```

---

## 7. Desk & portal

* **Workspace** "IT Service Desk" - 7 shortcuts, 8 number cards, 5 charts, 36 links.
* **Reports** (script): Service Desk Ticket Summary, SLA Compliance, SLA Violations,
  Engineer Performance, Ticket Aging, Ticket Analysis, Reopened Tickets, Monthly KPI,
  Change Success Report, Incident Report, Knowledge Base Usage, Top Requesters.
* **Ticket form** shows live SLA indicators, approve/reject buttons for the current
  approver, reassign, work log, article suggestions and one-click creation of a linked
  Incident / Problem / Change / Knowledge Article.
* **Portal** at `/support`: raise a request (with live article suggestions), track my
  tickets, search the knowledge base.

---

## 8. Tests

```bash
bench --site <site> run-tests --module \
  turacoz_service_desk.turacoz_it_service_desk.doctype.service_ticket.test_service_ticket
```

18 tests cover the priority matrix, working-hour deadline maths (including the weekend
skip), pause/resume, first response, resolution compliance, reopen, status-transition
guards, category routing, load balancing, the audit trail and approval matrix scoring.

---

## 9. Known gaps / next increments

* Teams, SMS and WhatsApp notification channels (the `Notification Sent` table already
  carries the channel field; only Email and System are wired up).
* Azure AD / Microsoft Graph, Jira import, GitHub and Slack integrations.
* CAB calendar view and a change freeze calendar.
* Portal attachment upload and in-portal ticket conversation (comments are API ready).
