# Changelog

## 1.0.1 — 2026-08-07

**Fixes**

* Number Card and Dashboard Chart filters were stored as `[fieldname, operator, value]`.
  The server accepts that shape, but the desk reads index 1 as the fieldname, so opening
  the workspace raised **"Invalid filter: not in"** on every load. Filters are now written
  in the desk format `[doctype, fieldname, operator, value, hidden]`.
* The "My Open Tickets" shortcut filtered on the literal string `"user"` instead of the
  logged-in user, so its count was always 0. `stats_filter` is evaluated as JavaScript by
  the desk, so it now uses `frappe.session.user`.

Both are repaired automatically by `bench migrate` (patch
`turacoz_service_desk.patches.v1_0.fix_dashboard_filter_format`), or manually with:

```bash
bench --site <site> execute turacoz_service_desk.turacoz_it_service_desk.setup.desk.run
bench --site <site> clear-cache
```

No schema or data migration is involved; only the 8 number cards, 5 charts and the
workspace shortcut definitions change.

## 1.0.0 — 2026-08-06

Initial release: 36 DocTypes, SLA / assignment / approval / notification / audit /
automation / knowledge engines, 12 reports, workspace with 8 number cards and 5 charts,
employee portal at `/support`, REST API, 18 unit tests.
