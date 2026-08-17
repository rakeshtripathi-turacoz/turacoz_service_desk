# Turacoz IT Service Desk — Production Installation Runbook

**Package:** `turacoz_service_desk-1.0.1.tar.gz`
**Target site:** `erp.turacoz.com`
**Platform:** ERPNext 15 / Frappe 15, Python ≥ 3.10, MariaDB 10.6+
**Estimated window:** 20–30 minutes (no downtime required, but a maintenance window is
recommended because `bench migrate` briefly puts the site into maintenance mode)

---

## 0. What this package installs

| Object | Count | Notes |
|---|---|---|
| DocTypes | 36 | 18 transactional/master + 18 child tables, module `Turacoz IT Service Desk` |
| Roles | 7 | Service Desk Executive / Engineer / Team Lead, Department Head, IT Manager, CISO, Auditor (existing roles are reused, never overwritten) |
| Script reports | 12 | SLA, performance, aging, KPI, change, incident, knowledge, requesters |
| Number cards / charts | 8 / 5 | On the "IT Service Desk" workspace |
| Workspace | 1 | "IT Service Desk" |
| Seed data | — | 60 service categories, 16 catalog services, 1 SLA policy, 1 team, 3 approval matrices |
| Portal page | 1 | `/support` (employee self service) |
| Scheduled jobs | 3 | every 15 min (SLA breach/escalation), hourly, daily |

**It does not modify ERPNext core, the `tms` app, or any existing DocType.**

---

## 1. Prerequisites

Run on the production server as the bench user (usually `frappe`):

```bash
cd /home/frappe/frappe-bench

bench version                       # frappe and erpnext must both be 15.x
bench --site erp.turacoz.com doctor # scheduler + workers must be healthy
python3 --version                   # 3.10 or newer
df -h .                             # at least 2 GB free
```

Requirements:

* `erpnext` installed on the site (this module links to Employee, Department, Asset,
  Project, Cost Center and Supplier).
* The scheduler must be **enabled** — SLA escalation, auto close and access expiry are
  scheduled jobs. Check with `bench --site erp.turacoz.com scheduler status`.
* An enabled outgoing **Email Account** if you want email notifications (in-app
  notifications work without one).

---

## 2. Back up first (mandatory)

```bash
cd /home/frappe/frappe-bench
bench --site erp.turacoz.com backup --with-files
ls -lh sites/erp.turacoz.com/private/backups | tail -4
```

Copy the backup off the server before continuing.

---

## 3. Transfer and unpack the package

From your workstation:

```bash
scp turacoz_service_desk-1.0.1.tar.gz frappe@<server>:/tmp/
```

On the server:

```bash
cd /tmp
sha256sum -c turacoz_service_desk-1.0.1.tar.gz.sha256   # must print: OK
tar xzf turacoz_service_desk-1.0.1.tar.gz               # creates /tmp/turacoz_service_desk
```

---

## 4. Add the app to the bench, then preflight

The package is a git repository (branch `main`), so `bench get-app` can consume it
directly. Use **Method A**; fall back to **Method B** if `bench get-app` is restricted on
your server.

**Method A — bench get-app**

```bash
cd /home/frappe/frappe-bench
bench get-app /tmp/turacoz_service_desk
```

**Method B — manual (this is the path used during the rehearsal on the staging copy)**

```bash
cd /home/frappe/frappe-bench
cp -r /tmp/turacoz_service_desk apps/turacoz_service_desk
./env/bin/pip install -e apps/turacoz_service_desk --no-deps
grep -qx turacoz_service_desk sites/apps.txt || echo turacoz_service_desk >> sites/apps.txt
./env/bin/python -c "import turacoz_service_desk; print(turacoz_service_desk.__version__)"   # 1.0.1
```

Neither method touches the database. Now run the read-only preflight check:

```bash
bench --site erp.turacoz.com execute \
    turacoz_service_desk.turacoz_it_service_desk.setup.preflight.check
```

Expected tail of the output:

```
No blockers. The app can be installed on this site.
```

The check reports:

* DocType / Report / Workspace **name clashes** with apps already on the site,
* roles that already exist (they are reused),
* missing ERPNext dependencies,
* scheduler, outgoing email and Holiday List warnings.

**If any blocker is listed, stop and report it — do not continue.** The only known clash
risk on a Turacoz site is the pre-existing `Service Category` DocType in the Turacoz
Management System module; this package deliberately names its own master
**`IT Service Category`** to avoid it.

---

## 5. Install

```bash
cd /home/frappe/frappe-bench
bench --site erp.turacoz.com install-app turacoz_service_desk
bench --site erp.turacoz.com migrate
bench build --app turacoz_service_desk
bench --site erp.turacoz.com clear-cache
bench restart
```

`install-app` runs, in order:

1. `before_install` — creates the 7 roles.
2. Module Def + import of all 36 DocType JSON files and the 12 report definitions.
3. `after_install` — seeds categories, the "Standard IT SLA" policy, the "IT Service Desk"
   team, the 3 approval matrices, 16 catalog services and Service Desk Settings, then
   builds the workspace, number cards and charts.

Expected final lines:

```
Desk artefacts ready.
Turacoz IT Service Desk: setup complete.
```

---

## 6. Verification

### 6.1 Command line

```bash
bench --site erp.turacoz.com console
```

```python
frappe.get_installed_apps()                                   # includes turacoz_service_desk
frappe.db.count("DocType", {"module": "Turacoz IT Service Desk"})   # 36
frappe.db.count("Report",  {"module": "Turacoz IT Service Desk"})   # 12
frappe.db.count("IT Service Category")                        # 60
frappe.db.count("Service Catalog")                            # 16
frappe.db.exists("Workspace", "IT Service Desk")              # "IT Service Desk"
frappe.db.get_value("SLA Policy", {"is_default": 1}, "name")  # "Standard IT SLA"
```

### 6.2 Automated tests

Run these on a **UAT copy** of the site if you can. If you run them on production, the
`--skip-before-tests` flag is **mandatory** — without it Frappe executes ERPNext's
`before_tests` hook, which creates a test company, fiscal year and other setup records on
the live site. The tests themselves insert records inside a transaction and roll back.

```bash
bench --site erp.turacoz.com run-tests --skip-before-tests \
    --module turacoz_service_desk.turacoz_it_service_desk.doctype.service_ticket.test_service_ticket
```

Expect `Ran 18 tests ... OK`. The suite covers the priority matrix, working-hour deadline
maths, SLA pause/resume, first response, resolution compliance, reopen, status-transition
guards, category routing, load balancing, the audit trail and approval matrix scoring.

### 6.3 In the browser

1. **Workspace** — `/app/it-service-desk` shows shortcuts, 8 number cards and 4 charts.
2. **Raise a ticket** — `/app/service-ticket/new`; check that Priority is derived from
   Impact × Urgency, a team is assigned and "Respond by"/"Resolve by" appear.
3. **Portal** — `/support` as a normal employee: raise a request, see "My Tickets".
4. **Report** — `/app/query-report/SLA Compliance` runs without error.
5. **Audit** — `/app/service-desk-audit-log` shows a "Created" row for the new ticket, and
   the row cannot be edited.

### 6.4 Scheduled jobs

```bash
bench --site erp.turacoz.com scheduler status     # must be Enabled
bench --site erp.turacoz.com show-pending-jobs
```

The three jobs to look for:

| Schedule | Method |
|---|---|
| `*/15 * * * *` | `...engine.automation.every_fifteen_minutes` (SLA breach + escalation) |
| hourly | `...engine.automation.hourly` (pre-breach reminders, access expiry) |
| daily | `...engine.automation.daily` (auto close, surveys, auto problem, audit purge) |

---

## 7. Post-install configuration

Do these before announcing the system to users.

1. **Service Desk Settings** (`/app/service-desk-settings`)
   * Confirm the default SLA policy and default team.
   * Toggle the modules you do not need (Change, Problem, CMDB, Privileged Access).
   * `Auto Close After (days)`, breach reminder %, audit retention (default 2555 days).

2. **Service Desk Team** (`/app/service-desk-team/IT Service Desk`)
   * Replace `Administrator` as Team Lead with the real lead.
   * Add engineers as members, set `Max Open Tickets` and the assignment method
     (Round Robin / Load Balancing / Skill Based / Manual).

3. **Roles** — assign `Service Desk Engineer`, `Service Desk Team Lead`,
   `Service Desk Executive`, `IT Manager`, `CISO`, `Auditor` to the right users.
   Every employee already holds `Employee`, which is enough to raise tickets.

4. **SLA Policy** (`/app/sla-policy/Standard IT SLA`)
   * Review response/resolution targets per priority.
   * Set the **Holiday List** so SLA working time excludes holidays.
   * Adjust business hours (default Mon–Fri 09:00–18:00) or tick 24×7.

5. **Approval matrices** — the seeded ones use `Requester Manager` (from
   `Employee.reports_to`), `IT Manager` and `CISO`. Confirm the reporting lines exist,
   otherwise approvals cannot resolve an approver.

6. **Engineer Skill** — add rows if you want skill-based routing.

7. **Categories and catalog** — prune or extend the 60 seeded categories and 16 services
   to match how Turacoz actually works.

8. **Portal link** — the "IT Service Desk" entry is added to the portal menu
   automatically; verify it appears at `/me` for a normal employee.

---

## 8. Optional: demo data for UAT

Only on a test/UAT site — **never on production**:

```bash
bench --site <uat-site> execute turacoz_service_desk.turacoz_it_service_desk.setup.demo.seed
bench --site <uat-site> execute turacoz_service_desk.turacoz_it_service_desk.setup.demo.purge
```

`seed` creates 60 tickets over 90 days plus incidents, changes, a problem and knowledge
articles so the dashboards and reports have something to show. `purge` removes exactly
what it created (tickets tagged `demo`, records prefixed `[DEMO]`).

---

## 9. Upgrading to a later version

```bash
cd /home/frappe/frappe-bench
bench --site erp.turacoz.com backup --with-files
cd apps/turacoz_service_desk && git pull        # or replace the folder from a new tarball
cd /home/frappe/frappe-bench
bench --site erp.turacoz.com migrate
bench build --app turacoz_service_desk
bench restart
```

Schema changes ship as DocType JSON and are applied by `migrate`; data changes ship as
patches listed in `turacoz_service_desk/patches.txt`.

---

## 10. Rollback

**Within the maintenance window, before users have entered data:**

```bash
bench --site erp.turacoz.com uninstall-app turacoz_service_desk --yes
bench --site erp.turacoz.com clear-cache
bench restart
```

`uninstall-app` drops the module's DocTypes **and their data**. The 7 roles and any
Holiday List you touched remain — remove them by hand if required.

**After users have entered data**, restore the backup taken in step 2:

```bash
bench --site erp.turacoz.com --force restore \
    sites/erp.turacoz.com/private/backups/<timestamp>-erp_turacoz_com-database.sql.gz
```

To simply switch the module off without removing it: disable the scheduled jobs and
remove the roles from users; the DocTypes stay but nothing runs.

---

## 11. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Module import failed for <DocType> ... No module named 'tms.turacoz_it_service_desk'` | Stale cache from a previous layout. `bench --site erp.turacoz.com clear-cache && bench restart` |
| Workspace, cards or charts missing | Re-run `bench --site erp.turacoz.com execute turacoz_service_desk.turacoz_it_service_desk.setup.desk.run` |
| Red popup **"Invalid filter: not in"** when the workspace opens | Number card / chart filters written by v1.0.0 in the short form. Fixed in 1.0.1 — `bench --site erp.turacoz.com migrate`, or `bench --site erp.turacoz.com execute turacoz_service_desk.turacoz_it_service_desk.setup.desk.run` then `bench --site erp.turacoz.com clear-cache` and reload the browser |
| "My Open Tickets" shortcut always shows 0 | Same v1.0.0 defect (literal `"user"` in the shortcut filter), fixed by the same command |
| Seed data missing (no categories/SLA) | Re-run `bench --site erp.turacoz.com execute turacoz_service_desk.turacoz_it_service_desk.setup.install.after_install` (idempotent) |
| SLA deadlines are blank | No SLA policy resolved. Check `Service Desk Settings → Default SLA Policy`, or that the category/service points at an active policy with a rule for that priority |
| SLA never escalates | Scheduler disabled or `pause_scheduler` set in site config |
| Emails not delivered | No enabled outgoing Email Account. Notifications are recorded as `Failed` in the ticket's "Notifications Sent" table; in-app alerts still work |
| "No approver could be resolved" | The approval level needs `Employee.reports_to` (Requester Manager) or a user holding the level's role |
| Employees can see other people's tickets | Confirm they do not hold a service-desk role; visibility is granted by role, then by requester/assignee |
| Report is empty | Widen the From/To date filters — they default to the last month |

Application errors are logged to `/app/error-log`; look for titles starting with
"Service desk".

---

## 12. Quick API reference

Base URL: `https://erp.turacoz.com/api/method/turacoz_service_desk.turacoz_it_service_desk.api.<module>.<method>`
Auth: `Authorization: token <api_key>:<api_secret>`

```bash
# create a ticket
curl -X POST "https://erp.turacoz.com/api/method/turacoz_service_desk.turacoz_it_service_desk.api.ticket.create" \
  -H "Authorization: token $KEY:$SECRET" \
  -d subject="VPN is down" -d category="VPN" -d ticket_type="Incident" -d urgency="High"

# live SLA state
curl "https://erp.turacoz.com/api/method/turacoz_service_desk.turacoz_it_service_desk.api.ticket.sla_status?ticket=TKT-2026-000001" \
  -H "Authorization: token $KEY:$SECRET"

# manager dashboard
curl "https://erp.turacoz.com/api/method/turacoz_service_desk.turacoz_it_service_desk.api.dashboard.manager" \
  -H "Authorization: token $KEY:$SECRET"
```

All endpoints return `{"success": true, "data": ...}` or
`{"success": false, "error": {"code": ..., "message": ...}}`.

Full endpoint list: `turacoz_service_desk/turacoz_it_service_desk/README.md`, section 6.

---

## 13. Sign-off checklist

- [ ] Backup taken and copied off the server
- [ ] Preflight reported no blockers
- [ ] `install-app` and `migrate` completed without errors
- [ ] 36 DocTypes, 12 reports, 60 categories, 16 services present
- [ ] 18 automated tests pass (with `--skip-before-tests` if run on production)
- [ ] Workspace, a test ticket and `/support` all work in the browser
- [ ] Scheduler enabled and the three jobs listed
- [ ] Team lead, members and roles configured
- [ ] SLA targets and Holiday List reviewed
- [ ] Approval matrices verified against real reporting lines
