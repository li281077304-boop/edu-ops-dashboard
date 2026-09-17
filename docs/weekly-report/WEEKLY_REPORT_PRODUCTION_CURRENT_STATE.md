# Weekly Report production pipeline state

## Scope

This branch adds the production runner around the already validated
`WeeklyReportSnapshot` v1.0. It does not change Payroll, Dashboard metrics, or
the four-week Golden definitions.

## Pipeline

`source-root` → `SOURCE_MANIFEST.json` → period resolution → completeness gate
→ `WeeklyReportSnapshot` → reconciliation/delta → SaaS snapshot boundary →
Excel renderer.

The stable source inbox is `weekly-report-data/`. Existing external WPS/TMS
exports can be passed as a controlled source root without copying or modifying
the original files.

## Real production dry run

- source root: `/Users/macos/Documents/03-周报数据/数学组周数据统计`
- latest available: `2026-06 week 4`
- latest complete: `2026-06-22 .. 2026-06-28`
- completeness: `COMPLETE`
- students single-subject: `263`
- 1v1 KS: `219`
- class KS: `411`
- equivalent hours: `356`
- teacher source rows: `18`
- output: `data/processed/production/`

The latest real source available on this machine is June 2026; no incomplete
later period is promoted. `refund` remains an explicit out-of-scope warning,
not an invented zero.

## Readiness

The production runner is deterministic for the same source hashes and includes
a next-week readiness regression using the same real workbook schema under a
new period name. API and web consumers read the production snapshot when it is
present; Excel is rendered from that same snapshot.
