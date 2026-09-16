# Recent-available weekly report UAT

There is no current-calendar-week raw source in the discovered workspace. The
latest complete, reproducible source pair is the real 2026-06-22—06-28
mathematics-group export (week 4). It was run through the same adapter and
template renderer as the historical Golden UAT.

- Snapshot: `week4.json`
- Generated workbook: `generated/generated_weekly_report.xlsx`
- Re-open inspection: `generated/generated_weekly_report.xlsx.inspect.ndjson`
- Render evidence: `generated/generated_weekly_report.xlsx.学生.png`
- Source: WPS `二校数学组数据汇总-六月第四周.xls` and TMS
  `排课列表_06月01日到06月28日_202606301011.xls`

The generated workbook is a real source-derived report, but it is
`PASS_WITH_WARNING`: `bkh` conversion/average metrics and a verified student
change/refund source remain unresolved; the source roster also contains
historical/special teachers and therefore does not assert a formal active
teacher denominator. No missing value is converted to zero.
