# Weekly Report 产品化 UAT 结果

本结果引用 `WEEKLY_REPORT_UAT.md`，不降低合同。真实 2026-06 四周 Golden 已重跑；最新可完整重放周期是 2026-06-22—06-28。2026-09 只有排课/课消来源，缺少对应 WPS 学生汇总和最终版，因此不冒充当前完整周报。

| UAT | 结果 | 证据/说明 |
|---|---|---|
| 01–04 | PASS | 资产、snapshot、学生、TMS 生产及 bkh 规则 |
| 05 | PASS_WITH_WARNING | 18 个 WPS 教师行；active roster 依赖 `teacher_config.py` 来源快照 |
| 06 | PASS_WITH_WARNING | `bkh = class_production_ks (KS)`、`C = I + N/3` 已由四周对账确认；平均课时/课次的 H/L/Q 调整分母仍缺 raw source |
| 07 | PASS_WITH_WARNING | `adjustments` 明确保存 RAW_CALCULATED、MANUAL_ADJUSTMENT、FINAL_CONFIRMED；当前四周没有可验证的人工调整记录 |
| 08 | PASS_WITH_WARNING | 当前完整周期与 18 人 `ACTIVE_TEACHERS` roster 一致；未来周期仍需新的 roster snapshot |
| 09 | PASS_WITH_WARNING | 4 周 Golden：`UNEXPLAINED_DIFFERENCE=0`，其余差异均为 MATCH 或 HISTORICAL_SOURCE_GAP |
| 10 | PASS_WITH_WARNING | 11 sheet 保留、Excel 可重开、错误公式扫描通过 |
| 11–12 | PASS_WITH_WARNING | LATEST_COMPLETE_PERIOD=2026-06-22—06-28；row/teacher/missing/duplicate 检查已落盘 |
| 13–16 | PASS | Weekly Report 已作为 `edu-ops-dashboard` 模块提供 snapshot service、HTTP API、Web 页面和同 snapshot Excel 导出 |
| 17 | PASS | 独立 Git branch `feat/weekly-report-p0` |
| 18 | TECHNICAL_OPEN | Ralph 隔离运行已产生 SELECT、Luna Worker、Machine Gate 证据，但 checkpoint/review 尚未完成；详见 `ralph_uat_evidence_20260916.md` |
| 19 | PASS | 技术/来源缺口保留为显式 unresolved，不静默变 0 |
| 20 | TECHNICAL_OPEN | Ralph durable checkpoint/review/final completion evidence 仍待正式 run；未伪造 PASS |

完整证据：`golden_uat_report.md`、`integrity_report.json`、`weekly_report_snapshot.json`、`weekly_report_latest.xlsx`。
