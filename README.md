# Turacoz IT Service Desk (TSD)

Enterprise ITSM and ticketing for **ERPNext 15 / Frappe 15**, built to the Turacoz ITSM PRD
v1.0 and aligned with ITIL practice: incidents, service requests, problems, changes,
privileged access, CMDB, knowledge base, SLA management, approvals, notifications, an
immutable audit trail, dashboards, reports and a REST API.

* **App name:** `turacoz_service_desk`
* **Module:** `Turacoz IT Service Desk`
* **Version:** 1.0.1
* **Requires:** Frappe v15, ERPNext v15, Python ≥ 3.10, MariaDB 10.6+

---

## Install

See **[INSTALL.md](INSTALL.md)** for the full production runbook (preflight, backup,
install, verification and rollback). The short version:

```bash
cd /home/frappe/frappe-bench
bench get-app /path/to/turacoz_service_desk-1.0.0.tar.gz
bench --site erp.turacoz.com execute \
    turacoz_service_desk.turacoz_it_service_desk.setup.preflight.check
bench --site erp.turacoz.com install-app turacoz_service_desk
bench --site erp.turacoz.com migrate
bench restart
```

`install-app` creates the roles, imports the 36 DocTypes and 12 reports, then seeds the
default categories, SLA policy, team, approval matrices, service catalog, workspace,
number cards and charts.

---

## What you get

| Area | Detail |
|---|---|
| Ticketing | Service Ticket with a 12-state workflow, work logs, public/internal comments, watchers, feedback, attachments, related records |
| ITIL | Incident, Problem, Change Request (CAB, risk, rollback), Privileged Access Request with expiry and auto revocation |
| SLA | Per-priority response/resolution targets in **working time**, holidays, pause/resume, breach detection, multi-level escalation |
| Assignment | Round robin, load balancing, skill based (Engineer Skill) or manual, mirrored into ToDo |
| Approvals | Approval Matrix with role/user/manager/department-head/CISO levels, sequential or parallel, python conditions |
| Knowledge | Articles with versioning and approval, auto-suggestion on ticket text, one-click article from a resolved ticket |
| CMDB | Configuration Items with relationships, environment, criticality, linked ERPNext Assets |
| Audit | Append-only Service Desk Audit Log (user, IP, user agent, field diff), 7-year retention default |
| Analytics | 12 script reports, 8 number cards, 5 charts, 4 dashboard APIs (employee / engineer / manager / executive) |
| Portal | `/support` self-service page for employees |
| API | Token-authenticated REST endpoints with a consistent JSON envelope |

Full technical documentation: [`turacoz_service_desk/turacoz_it_service_desk/README.md`](turacoz_service_desk/turacoz_it_service_desk/README.md)

---

## Layout

```
turacoz_service_desk/
├── INSTALL.md                     production runbook
├── pyproject.toml                 flit packaging
└── turacoz_service_desk/
    ├── hooks.py                   doc events, scheduler, permissions, portal menu
    ├── modules.txt                Turacoz IT Service Desk
    ├── www/support/               employee self service portal
    └── turacoz_it_service_desk/
        ├── api/                   REST endpoints
        ├── doctype/               36 DocTypes + controllers + client scripts + tests
        ├── engine/                sla, assignment, approval, notification, audit,
        │                          automation, knowledge, utils
        ├── report/                12 script reports
        └── setup/                 install, desk, demo, preflight
```

---

## Roles

`Employee`, `Service Desk Executive`, `Service Desk Engineer`, `Service Desk Team Lead`,
`Department Head`, `IT Manager`, `CISO`, `Auditor`.

Employees see only their own tickets (enforced by a permission query condition); Auditor is
read-only; the audit log is visible only to System Manager, IT Manager, CISO and Auditor.

---

## Support

Raised and maintained by the Turacoz IT team — it@turacoz.com.
# helpdesk
# helpdesk
# turacoz_service_desk
