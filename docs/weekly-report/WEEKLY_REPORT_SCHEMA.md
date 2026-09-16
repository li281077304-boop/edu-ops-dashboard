# Weekly Report canonical schema（来自真实 2026-06 数学组周报）

## Report envelope

每一份报告对应一个 `period`（`period_start`、`period_end`、`week_label`、`group`、`campus`），并由原始来源适配器生成不可变 `WeeklyReportSnapshot`。Excel 只是一个渲染目标，不是领域真相。

```text
WeeklyReportSnapshot
├── period
│   ├── year / month / week_label / start / end
│   ├── group / campus
│   └── source_revision
├── students
│   ├── one_to_one: primary_scope, high_school, double_three
│   ├── class: primary_scope, high_school, double_three
│   ├── changes: stop, new, completed, refund (1v1/class)
│   ├── single_subject_total
│   ├── class_count
│   └── collaboration_part_time_count
├── fullness
│   ├── grade_buckets and class_size_buckets
│   └── rates (per bucket + total)
├── production
│   ├── weekly / month_to_date production hours
│   ├── weekly / month_to_date average hours and sessions (only when H/L denominator source is present)
│   ├── one_to_one production KS
│   ├── class production KS / class count / teacher sessions
│   └── special_teaching
├── teachers[]
│   ├── teacher_id/name/status
│   ├── one_to_one students/hours/weekly_average
│   ├── class students/classes/average_class_size
│   ├── subject_count/hours/sessions
│   ├── leave/extra/expansion
│   └── renewal/referral heads/hours
├── manual_adjustments[]
├── warnings[]
├── unresolved_items[]
└── provenance[]
```

## Sheet/section contracts

| section | stable fields / purpose | source class |
|---|---|---|
| `学生` | 单科数；1v1 初小/高中/双三、停课、新增、结课、退费；班课同类字段；开班数、协作兼职数 | WPS/周数据台账 + explicit manual adjustment |
| `满班率` | 小学、初中、高中及特殊班型（1对2/1对3）的学生数、班级容量、分组率、总单科数、总容量、总满班率 | WPS class-size data; formulas are derived |
| `教师` | 1v1/班课 students, hours, weekly average, class count/average, total subjects/hours/sessions, leave/extra/expansion, renewal/referral | WPS teacher summary + TMS + renewal/referral workbook |
| `组课时生产` | 月/周生产课时；综合平均课时/课次；1v1 与班课生产 KS；教师数；特殊授课 R/S | TMS hard authority, WPS for denominator |
| `回访检查` | 微信/电话/班课回访应回访/实回访、名单 | manual operational input |
| `教研培训` | 听课、刷题、教研活动、培训记录 | manual operational input |
| `本周工作与问题` / `下周工作计划` / `欣赏之窗` | 文字、重点工作、问题、计划、表扬 | manual narrative input |

## Semantic rules

- `单科数 = 1v1初小 + 1v1高中 + 班课初小 + 班课高中`；双三是父级口径的重叠子集，只展示，不重复计入。
- 学生数与新增/结课/停课来自 WPS/周数据台账；不能只用周间差值反推变化。
- 课时生产、1v1/班课及特殊授课以 TMS 排课为硬来源；已上课按实到，未上课按应到（具体课时当量需以已确认单位为准）。
- 真实 2026-06 WPS/TMS 对账确认：`bkh = class_production_ks`，单位为 KS；`N = bkh`，总课时当量为 `1v1_KS + bkh / 3`。依赖人工调整后的 H/L 分母的平均指标仍在缺源时保持未决，不自动填零。
- 教师姓名先规范化空白，只有唯一匹配才归属；兼职/转组教师不自动计入正式教师数。
- 手动最终版是每周历史标准；自动生成只可对账，不能用魔法数字追平人工修正。
- 缺失、冲突、期间不明、单位不明、无法唯一归属均进入 `warnings/unresolved_items`，不能静默解释为 0。
