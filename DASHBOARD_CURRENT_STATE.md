# Dashboard Current State — Ralph bootstrap

## Evidence basis

- Repository: `edu-ops-dashboard`
- Starting branch: `feature/yesterday-excel-dashboard-cards`
- Starting HEAD: `431fab8`
- Existing implementation: `src/edu_ops/dashboard.py` reads a frozen schedule export through the existing Excel adapter, normalizes rows into `ScheduleRecord`, computes documented production/planned/weekly/monthly metrics, and serves responsive read-only cards.
- Existing validation: repository tests and ruff checks are present; historical screenshots are in `artifacts/`.
- Product boundary: Dashboard is an Education Operations SaaS module. Excel/CSV is an input adapter; the UI consumes normalized dashboard payload rather than Excel cells directly.

## Real input used for this bootstrap

- Path: `/Users/macos/Downloads/排课列表_08月31日到09月27日_202609131718.xls`
- SHA-256: `647075195f101c998474d0d57a4bef7206fb38bc8faab88713696bbd92698544`
- Size: `133252` bytes
- Sheet: `排课记录-08月31日到09月27日`
- Observed rows: `1092`
- Teachers: `44`
- Observed record range: `2026-09-02` to `2026-09-27`
- Reporting period resolved from `config/manual_months.csv`: `2026-08-31` to `2026-09-27`, artificial month 9, 4 weeks
- Download pipeline: not touched; this is a frozen existing export.

## Confirmed product capabilities

- Existing metric definitions are documented in `docs/指标口径.md`.
- Existing cards are mobile-first and expose production hours, planned hours, monthly averages, weekly average lessons, and teacher count.
- Android home-screen widget is a tracked future obligation; this bootstrap does not claim it is implemented or deployed.

## Open boundaries

- PostgreSQL/Metabase production deployment is not available in this environment.
- Production KPI exclusions for gifted/relative-gift/schedule-only lessons remain a business-rule boundary documented by the project.
- Real Android widget installation is not verified here.
