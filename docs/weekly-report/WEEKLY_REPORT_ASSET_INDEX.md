# 学科组长周报资产索引（Discovery 记录）

更新时间：2026-09-16

本索引只记录本机已发现的真实资料及其角色；未把文件名或用户观察自动升级为业务事实。当前没有发现一个独立的 Weekly Report Git/SaaS 仓库；真实资料集中在本目录、桌面周报目录、知识库邮件附件，现有自动化脚本集中在数学组周数据统计目录。

## 主闭环数据集（2026 年 6 月数学组）

| 文件 | 角色 | 时间范围 | 可解析性 | 备注 |
|---|---|---|---|---|
| `数学组周数据统计/数学组数据统计表基础模板.xlsx` | TEMPLATE | 2026-06 | OOXML/XLSX，可用 openpyxl/artifact-tool | 作为稳定版式与 sheet 结构来源 |
| `数学组周数据统计/数学组数据统计表-宣城二校6月第1周(2).xls` | FINAL_GOLDEN | 2026-06 第1周 | 标准 CDFV2，可用 xlrd | 学生、满班率、教师、组课时生产等最终版 |
| `数学组周数据统计/数学组数据统计表-宣城二校6月第2周——手动数据.xls` | FINAL_GOLDEN | 2026-06 第2周 | 标准 CDFV2，可用 xlrd | 手动最终标准 |
| `数学组周数据统计/数学组数据统计表-宣城二校6月第3周——手动数据.xls` | FINAL_GOLDEN | 2026-06 第3周 | 标准 CDFV2，可用 xlrd | 手动最终标准 |
| `数学组周数据统计/数学组数据统计表-宣城二校6月第4周——手动数据.xls` | FINAL_GOLDEN | 2026-06 第4周 | 标准 CDFV2，可用 xlrd | 手动最终标准 |
| `数学组周数据统计/二校数学组数据汇总-六月第三周.xls` | RAW_INPUT | 2026-06 第3周 | 标准 CDFV2，可用 xlrd | WPS/周数据汇总，学生变化与教师输入 |
| `数学组周数据统计/二校数学组数据汇总-六月第四周.xls` | RAW_INPUT | 2026-06 第4周 | 标准 CDFV2，可用 xlrd | WPS/周数据汇总，学生变化与教师输入 |
| `数学组周数据统计/排课列表_06月01日到06月28日_202606231621.xls` | RAW_INPUT | 2026-06-01—06-28 | 实为 OOXML，需按 file 检测后用 openpyxl | TMS 排课/课时生产来源 |
| `数学组周数据统计/排课列表_06月01日到06月28日_202606301011.xls` | RAW_INPUT | 2026-06-01—06-28 | 实为 OOXML，需按 file 检测后用 openpyxl | 更新版 TMS 排课来源 |
| `数学组周数据统计/2026年度续费+推荐数据(2).xlsx` | RAW_INPUT | 2026-06 | OOXML/XLSX，可机器解析 | 教师页续费/推荐权威来源候选 |
| `数学组周数据统计/2026年度续费+推荐数据(3).xlsx` | RAW_INPUT | 2026-06—07 | OOXML/XLSX，可机器解析 | 后续续费/推荐来源候选 |
| `数学组周数据统计/宣城二校退费统计表2026年.xls` | RAW_INPUT | 2026-06 | CDFV2，可用 xlrd | 退费辅助来源；不纳入本 P0 核心范围 |
| `数学组周数据统计/2026春季班课表6.24.xlsx` | RAW_INPUT | 2026 春季 | OOXML/XLSX | 班课/班级辅助来源 |

该数据集有连续 4 个具备原始汇总与最终版的周次，优先用于至少 3 周 Golden UAT。历史最终版之间存在人工修正与累计差异，自动生成结果必须将 MATCH、EXPECTED_DIFFERENCE、UNEXPLAINED_DIFFERENCE 分开记录。

## 桌面理化组周报资产

根目录：`/Users/macos/Desktop/周报/`

| 文件 | 角色 | 时间范围 | 可解析性 | 备注 |
|---|---|---|---|---|
| `理化数据统计表——七月第五周.xlsx` | FINAL_GOLDEN / HISTORICAL_REPORT | 2026-07 | XLSX | 9 个稳定 sheet，含月度基底 |
| `理化数据统计表——八月第一周手动.xlsx` | FINAL_GOLDEN / MANUAL_FINAL | 2026-08 第1—2周 | XLSX | 含人工调整痕迹 |
| `理化数据统计表——八月第2周.xlsx` | FINAL_GOLDEN / HISTORICAL_REPORT | 2026-08 第1—2周 | XLSX | 第二周历史版 |
| `理化数据统计表——八月第一周_备份(填写前).xlsx` | TEMPLATE / PRE-FILL_BACKUP | 2026-08 第1周 | XLSX | 结构完整，填报前备份 |
| `理化数据统计表——八月第一周手动_备份(填第2周前).xlsx` | HISTORICAL_REPORT | 2026-08 第1周 | XLSX | 第二周尚未填写 |
| `理化数据统计表——八月第一周手动_备份(双三修正前).xlsx` | HISTORICAL_REPORT | 2026-08 第1周 | XLSX | 双三修正前对照 |
| `理化数据统计表——八月第一周_我按接龙算的版本.xlsx` | DRAFT | 2026-08 第1周 | XLSX | 与手动版有已记录口径差异，不作 Golden |

理化周报稳定含：`学生`、`满班率`、`教师`、`组课时生产`、`回访检查`、`教研培训`、`本周工作与问题`、`下周工作计划`、`欣赏之窗`。

## 中间层与既有产物

| 路径 | 角色 | 覆盖 | 备注 |
|---|---|---|---|
| `/Users/macos/Documents/做表/outputs/math-weekly-ledger-prototype/数学组6月第4周-周数据台账原型.xlsx` | PROTOTYPE / LEDGER | 2026-06 第4周 | 含“周数据台账”“人工修正账” |
| `/Users/macos/Documents/做表/outputs/math-student-ledger-sample/数学组学生状态与停课核对台账样表.xlsx` | PROTOTYPE / LEDGER | 历史数学组 | 学生状态、每周变动、月度停课核对 |
| `/Users/macos/Documents/做表/数学组周报_Codex投递区/2026年7月第1周/学生快照.xlsx` | RAW_INPUT / STUDENT_SNAPSHOT | 2026-06-29—07-05 | 数学组学生最终数确认入口 |
| `/Users/macos/Documents/做表/outputs/理化组_2026年8月第1周_简化周报/理化组_2026年8月第1周_简化周报_草稿.xlsx` | DRAFT / GENERATED_OUTPUT | 2026-08 第1周 | 由 `.codex-weekly/build-aug-week1-draft.mjs` 生成 |

## 既有代码与工具

目录：`/Users/macos/Documents/03-周报数据/数学组周数据统计/`

- `auto_weekly.py`：旧版自动填报，WPS 学生/变化 + TMS 排课 + 满班率/教师/组课时生产；固定假设较多，必须先过字段与单位预检。
- `weekly_auto.py`、`auto.py`、`auto_fill.py`、`fill_*`、`week2_detail.py`：历史/局部自动化工具，不视为默认执行器。
- `weekly_report.py`：从既有教师/学生 sheet 生成 Markdown/Excel 摘要；可复用其列映射与来源记录，但不能替代规范化快照。
- `teacher_config.py`：区分 `ALL_TEACHERS`、`ACTIVE_TEACHERS`、特殊/兼职教师。
- `/Users/macos/Documents/做表/.codex-weekly/*.mjs`：模板检查与简化版草稿生成工具，使用 artifact-tool。

## Skill / 规则来源

- `/Users/macos/.codex/skills/math-weekly-report/SKILL.md`
- `/Users/macos/.codex/skills/math-weekly-report/references/business-rules.md`
- `/Users/macos/.codex/skills/math-weekly-report/references/verification-rules.md`
- `/Users/macos/.codex/skills/math-weekly-report/references/simplified-first-week.md`
- `/Users/macos/.codex/skills/math-weekly-report/references/legacy-implementation.md`
- `/Users/macos/.codex/skills/排课预排统计/SKILL.md`

关键规则已核实：TMS 是课时生产权威来源；WPS/周数据台账是学生数与变化来源；手动最终版是历史标准；双三是父级口径的重叠子集，不重复计入单科总数；`bkh` 单位未确认前不得计算依赖它的生产指标；未知不能静默填 0；学生新增/结课不能仅由周间人数差推断。

## 更广泛历史周报

- `/Users/macos/Documents/03-周报数据/宁国一校-周报业绩与培训/`：含 DOS/周报相关历史资料。
- `/Users/macos/Documents/知识库/工作知识库/网易邮箱邮件/收件箱/2024/`、`2025/`、`2026/`：含大量学科组长周报邮件文本（2024—2026），适合作为跨年度结构和人工叙述区参考，但邮件正文通常不含可直接复算的附件表格。
- `/Users/macos/Documents/知识库/工作知识库/网易邮箱邮件/已发送/附件/`：历史邮件附件候选来源。

## 当前发现结论

1. 已找到真实模板、至少 4 个连续数学组最终版周次、真实 WPS/TMS/续推来源、既有脚本和相关 skill。
2. 没有发现独立现成的 Weekly Report SaaS Git 仓库；当前应将规范化快照与渲染器设计为可接入 Education Operations SaaS 的独立适配层。
3. P0 先聚焦学生、课时生产、教师三域；回访/教研/工作计划/欣赏之窗属于文本或人工区，后续按证据处理。
4. 下一步是基于主闭环数据集完成 `WEEKLY_REPORT_SCHEMA.md`、`WEEKLY_REPORT_METRICS.json`、`WEEKLY_REPORT_SOURCE_MAP.json`，再实现规范化快照和生成器；任何无法从权威来源确认的字段必须留为 `SOURCE_MISSING`、`BUSINESS_RULE_MISSING` 或 `MANUAL_ONLY`。

## 本轮可复核产物

- `outputs/weekly-report-uat/golden_uat_report.json` / `.md`：2026-06 连续 4 周真实 WPS/TMS → 历史最终版对账；`UNEXPLAINED_DIFFERENCE=0`，并保留历史人工/来源差异。
- `outputs/weekly-report-uat/weekly_report_snapshot.json`：最新可复现第 4 周规范化快照（2026-06-22—06-28）。
- `outputs/weekly-report-uat/generated/generated_weekly_report.xlsx`：从真实模板 + snapshot 生成并重开核验的 Excel。
- `outputs/weekly-report-uat/current_week_uat.md`：当前周输入缺失说明及最近可用周次 UAT 记录。
