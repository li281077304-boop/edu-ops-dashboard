# Weekly Report Module — SaaS boundary

The report is a module of Education Operations SaaS, not an Excel-shaped
business core:

```text
WPS/TMS/CSV adapter (P0) ─┐
SaaS database adapter     ├─> WeeklyReportSnapshot ─> web view / Excel export
future API adapter       ─┘
```

Adapters own file/schema recognition and provenance. The domain service owns
student, production, teacher and fullness semantics. Renderers own the
historical workbook layout. `weekly_report_module/weekly_report.py` is the
current P0 adapter; it does not import Payroll or Dashboard code.

The snapshot deliberately carries `warnings`, `unresolved_items`,
`manual_adjustments`, and source hashes. A SaaS adapter can produce the same
shape without changing the renderer or the Golden UAT comparison.
