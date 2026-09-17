# SaaS runtime evidence

Started `python3 -m edu_ops.weekly_report.server` with the production snapshot.

- `/weekly-report/healthz` → HTTP 200
- `/weekly-report/api` → `2026年6月第4周`, `COMPLETE`, 18 teacher rows
- `/weekly-report/export` → HTTP 200, 26,665-byte XLSX

The web/API/export paths therefore consume the same production snapshot.
