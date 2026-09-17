# Weekly Report Production UAT

This is the acceptance contract for the weekly production pipeline. The
`WeeklyReportSnapshot` is the only business truth; the SaaS API, web view and
Excel export are renderers of the same snapshot.

## Required gates

- **UAT-01 Source inbox and provenance**: discover WPS/TMS/CSV/XLS/XLSX inputs,
  classify them using content/schema evidence, and persist `SOURCE_MANIFEST.json`
  with hashes, periods and provenance.
- **UAT-02 Period resolution**: distinguish `LATEST_AVAILABLE_PERIOD` from
  `LATEST_COMPLETE_PERIOD`; never promote a partial period to final.
- **UAT-03 Completeness**: evaluate `COMPLETE`, `PARTIAL`, or `INVALID` for the
  student, production, teacher and active-roster source set. Missing values are
  not zero.
- **UAT-04 Snapshot**: produce deterministic `WeeklyReportSnapshot` v1.x with
  students, production, teachers, adjustments, warnings, source metadata and
  source hashes.
- **UAT-05 Reconciliation**: record row counts, duplicates, unmapped entities,
  key totals and week-over-week deltas with WARNING/BLOCKING severity.
- **UAT-06 SaaS**: API and web view consume the snapshot, show period,
  completeness, source warnings and previous-period deltas.
- **UAT-07 Excel**: export `weekly_report_<period>.xlsx` from the snapshot,
  reopen it, scan formulas/errors and verify key cells.
- **UAT-08 One-command/idempotency**: one production command runs discovery →
  completeness → snapshot → reconciliation → API store → Excel export. A
  repeated run with the same source hashes produces the same business snapshot.
- **UAT-09 Historical regression**: all four existing Golden periods remain
  `UNEXPLAINED_DIFFERENCE = 0`.
- **UAT-10 Latest real period**: run against the newest complete real input and
  persist the selected period and evidence.
- **UAT-11 Next-week readiness**: adding a new schema-compatible period without
  code/config/rule changes is discovered and becomes the latest complete period.
- **UAT-12 Ralph delivery**: the production run has durable Chief, Luna Worker,
  Machine Gate, checkpoint and final status evidence; required gate failures
  fail closed.

Human escalation is limited to the existing Core categories. File discovery,
format errors, parsing, matching, tests and SaaS bugs remain technical work.
