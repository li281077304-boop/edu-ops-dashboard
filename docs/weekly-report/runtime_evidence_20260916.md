# SaaS runtime evidence (2026-09-16)

Command: `uv run python apps/weekly-report-server.py`

- `GET /weekly-report/healthz` returned `{"status":"ok","module":"weekly-report"}`.
- `GET /weekly-report/api` returned period `2026年6月第4周`, single-subject students
  `263`, 1v1 production `219 KS`, class production `411 KS`, active roster `18`.
- `GET /weekly-report` rendered the Chinese title and the same three card values.
- `GET /weekly-report/export` returned HTTP 200 with an XLSX content type and a
  Microsoft Excel 2007+ file.

The runtime reads `data/processed/weekly_report_snapshot.json`; no web-layer
calculation is performed.
