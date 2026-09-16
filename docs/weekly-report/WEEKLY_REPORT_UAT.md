# 学科组长周报产品化 UAT 合同

版本：`1.0`  约束日期：2026-09-16

本文件是本轮唯一验收合同。后续实现、Machine Gate、Ralph handoff/review 均引用它，不降低标准。领域真相是 `WeeklyReportSnapshot`；Excel 只负责渲染，Web/API 与 Excel 必须消费同一份 snapshot。

## UAT 清单

| ID | 验收目标 | PASS 条件 | 证据 |
|---|---|---|---|
| UAT-01 | 资产可追溯 | 模板、最终版、历史、skill、WPS/TMS/CSV 均有路径、角色、周期、hash/provenance | `WEEKLY_REPORT_ASSET_INDEX.md` |
| UAT-02 | Domain Schema | 学员、课时生产、教师由 snapshot 表达，业务计算不依赖 Excel | schema + snapshot |
| UAT-03 | 学员指标 | 单科、1v1/班课年级、停课/新增/结课、开班数及历史 P0 指标有真实来源 | source map + tests |
| UAT-04 | 课时生产 | 1v1 KS、班课 KS、周生产、教师课次及真实大/小周口径均有历史证据 | source map + Golden |
| UAT-05 | 教师指标 | 名单、1v1/班课学生、班级、课时、课次、扩科、active/inactive 有正式来源 | roster + snapshot |
| UAT-06 | bkh/平均指标 | 单位、分母、周期、公式已由一致证据固化；否则明确 Human Boundary | rules artifact |
| UAT-07 | 学生变化 | RAW_CALCULATED + 明确 MANUAL_ADJUSTMENT = FINAL_CONFIRMED，调整有 reason/source/period/metric | adjustment bridge |
| UAT-08 | active roster | 系统可从权威名单/排课/人事建立 roster；仅冲突才需要人 | roster evidence |
| UAT-09 | Golden regression | 至少 4 周重新生成并对账，`UNEXPLAINED_DIFFERENCE=0` | Golden report |
| UAT-10 | Excel renderer | 模板结构/关键 sheet 保留，可重开，无 `#REF!/#VALUE!/#NAME?` | generated XLSX |
| UAT-11 | latest period | 自动发现最新完整原始周次并生成 snapshot/report，标记 `LATEST_COMPLETE_PERIOD` | latest index |
| UAT-12 | 数据完整性 | row/teacher/student、duplicate、unmapped、异常 delta 均显式报告 | integrity report |
| UAT-13 | SaaS domain | Weekly Report 归属于 Education Operations SaaS，不是桌面孤立脚本 | product repo |
| UAT-14 | SaaS service/API | API/service 返回 period、students、production、teachers、warnings、source metadata | runtime evidence |
| UAT-15 | SaaS Web | “学科组长周报”页面真实运行，P0 三大域可读 | browser/runtime evidence |
| UAT-16 | SaaS Excel export | Web/API 与 Excel 共用同一 snapshot 生成结果 | export evidence |
| UAT-17 | Git ownership | 正式代码位于有 branch/commit/tests/UAT 的 Git repo，桌面原始文件不动 | git evidence |
| UAT-18 | Ralph loop | 真实 Chief → Luna Worker → Gate → checkpoint → Review → next obligation | Ralph artifacts |
| UAT-19 | Human Boundary | 技术问题不问人；仅允许业务/来源确认等类别，global wait 有 deterministic gate | obligations |
| UAT-20 | Durable completion | UAT、schema、source map、snapshots、Golden、latest、Excel、SaaS、Ralph evidence 均落盘 | artifact index |

## 状态口径

每项状态只能是 `PASS`、`TECHNICAL_OPEN`、`HUMAN_BLOCKED` 或 `NOT_TESTED`。历史人工修正必须单列，不能改算法凑匹配；空值不得静默变成 0。
