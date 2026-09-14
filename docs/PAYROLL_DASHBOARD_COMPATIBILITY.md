# Payroll / Dashboard Compatibility Matrix

审计范围：Dashboard `fix/sol-review-1` 基线 `c70b4f2`，以及本机只读 sibling repo `education-payroll` 的 `feature/payroll-ui-v1`。本文件不修改 Payroll，也不把两套内部 `ScheduleRecord` 合并。

结论先行：两边可以通过各自 adapter 映射到 canonical contract 的公共事实，但当前不能直接无损互换。教师身份、校区/学科 ID、来源记录 ID、来源版本和完整 provenance 必须在未来共享发布边界补齐。

状态只使用三种：`DIRECT`、`ADAPTER`、`BLOCKED`。`BLOCKED` 表示当前输入不足以安全映射，不表示可以用显示名或猜测值补齐。

最小 prototype 位于 `src/edu_ops/compatibility.py`，只提供
`Dashboard ScheduleRecord → CanonicalScheduleRecord` 和
`Payroll ScheduleRecord-shaped input → CanonicalScheduleRecord` 两条纯函数路径；它不依赖 Payroll package，也不改变任一系统内部模型。

## 字段级矩阵

| CANONICAL_FIELD | PAYROLL_SOURCE | DASHBOARD_SOURCE | SEMANTIC_MATCH | TYPE_MATCH | LOSSLESS_MAPPING | RISK | ADAPTER_NEEDED |
|---|---|---|---|---|---|---|---|
| `source_record_id` | `ScheduleRecord` 无字段；排课 Excel 也未见稳定记录 ID | QueryNew 原始 `ID` 存在，但当前 `ScheduleRecord` 未保留 | 否 | 未知 | `BLOCKED` | 导出行号或拼接字段不能证明跨版本稳定 | `BLOCKED` |
| `lesson_date` | `lesson_time` 中正则提取 `YYYY-MM-DD`，类型为 `str` | `lesson_date`，类型为 `date` | 是 | 否 | `ADAPTER` | Payroll 缺失/异常日期目前作为空字符串 | `ADAPTER` |
| `teacher_id` | `ScheduleRecord.teacher`、`PayrollRecord.teacher` 使用姓名字符串 | `TeacherID/教师ID`；无 ID 时保持空值 | 否 | 否 | `BLOCKED` | Payroll 当前姓名是对账和工资表键，无法证明是 canonical ID | `BLOCKED` |
| `campus_id` | `ScheduleRecord` 无校区字段 | `campus` 只有清洗后的展示名称 | 否 | 否 | `BLOCKED` | 两边都没有可解析的 canonical 校区 ID | `BLOCKED` |
| `subject_id` | `subject` 是展示学科文本并清理数字前缀 | `subject` 是展示学科文本并清理数字前缀 | 部分 | 否 | `BLOCKED` | 文本相同不等于稳定学科 ID | `BLOCKED` |
| `student_or_class` | `student`、`class_name` 两个展示/溯源字段 | `student_id`，没有 class ID/name 字段 | 部分 | 否 | `ADAPTER` | 班课学生/班级语义不对称 | `ADAPTER` |
| `class_type` | `normalize_class_type`：`1对1`、`1对2`、`小班` | 当前保存原始 `course_type`；prototype 对已知形式做同样归一 | 部分 | 否 | `ADAPTER` | 特殊班型、领航等不可猜测 | `ADAPTER` |
| `lesson_status` | 保存原始 `lesson_status`，工资规则主要筛 `已上课` | 保存原始 `status`，取消规则另行识别 | 是（经标准化） | 是 | `ADAPTER` | `已取消/作废/未上课` 的排除边界需统一枚举 | `ADAPTER` |
| `attended` | `Optional[int]`，缺失为 `None` | `Optional[Decimal]`，来自实到人数；缺失保持 `None` | 是：人数 | 否 | `ADAPTER` | 不能把缺失、0、布尔出勤混为一谈 | `ADAPTER` |
| `duration` | `duration_text: str`；可能没有独立时长列而退回整段时间文本 | `lesson_hours: Decimal`，已转为小时 | 部分 | 否 | `ADAPTER` | Payroll 只有显式“小时/分钟”时才能无损转换 | `ADAPTER` |
| `source` | 原始文件路径字符串 | API/Excel source 标签或路径 | 部分 | 是 | `ADAPTER` | 来源系统、通道和文件路径混在同一字符串 | `ADAPTER` |
| `source_version` | 无字段 | 无字段 | 否 | 否 | `BLOCKED` | 不能用 Git SHA 或文件名猜来源 schema 版本 | `BLOCKED` |
| `source_run_id` | UI `RunStore.runs.id` 为 UUID；文件记录保存于 run state | 指标行可选 `source_run_id`；采集运行记录另存 JSONL | 部分 | 是 | `ADAPTER` | Dashboard 目前不是 ScheduleRecord 的必备字段 | `ADAPTER` |
| `source_file` | `RunStore` 保存 path；`SourceEvidence` 保存 source_file | `FileValidation.path`；文件校验器生成路径 | 是 | 否 | `ADAPTER` | 绝对路径不适合跨系统传播 | `ADAPTER` |
| `source_hash` | `RunStore.import_file` 计算 SHA-256 | `FileValidation.sha256` 计算 SHA-256 | 是 | 是 | `ADAPTER` | 两边尚未形成共同 provenance 发布记录 | `ADAPTER` |
| `snapshot_at` | run `created_at` 是任务创建时间，不是源数据读取时间 | `retrieved_at` 是读取时间，`snapshot_date` 是业务快照日 | 部分 | 否 | `ADAPTER` | 不能把业务日和采集时刻互相替代 | `ADAPTER` |
| `period` | `ScheduleRecord.period` 直接保存 `YYYY-MM` | 人工月由配置解析；指标保存 period start/end，记录本身无 period | 部分 | 否 | `ADAPTER` | 自然月与人工月不能混用 | `ADAPTER` |
| `rule_version` | 无统一字段；规则散落在 Skill/Excel/脚本 | 无字段；指标代码版本未写入行 | 否 | 否 | `BLOCKED` | 无法重现某次人工/业务规则版本 | `BLOCKED` |
| `generated_at` | run `created_at` 可作为运行生成时刻 | 数据库 `created_at` 是写库时刻；没有显式生成时刻 | 部分 | 是 | `ADAPTER` | 写库时刻不一定等于指标计算时刻 | `ADAPTER` |

## 重点语义审计

### duration

canonical 约定为“小时数”，类型建议 `Decimal`。Dashboard 的 `Duration` 分钟和“小时/分钟”文本可以转换；Payroll 的 `duration_text` 是文本，且没有上课时长列时可能退回整段 `上课时间`，此时不能解析就必须 `BLOCKED`。不能把课次、lesson factor 或人数系数当作 duration。

### attended

canonical 是“实到人数”，不是布尔值。Dashboard 还保留 expected/attended 的来源对，Payroll 使用 `Optional[int]`；两边都区分 0 与缺失。Dashboard 的 canonical adapter 只读取 `attended_students`，不会用 expected 补齐 attended。

### lesson_status

prototype 统一为 `COMPLETED`、`SCHEDULED`、`CANCELLED`、`VOIDED`。Dashboard 已取消/作废课从经营指标排除；Payroll 当前标准排课记录保存原文，工资规则主要只保留“已上课且实到大于 0”，因此不能宣称两套排除逻辑已经等价，必须经 adapter 和契约测试。

### class_type

`1对1` 映射为 `1对1`；`1对2` 保持多人课，不得误判为一对一；`集体班/6人班/8人班/10人班` 可映射为 `小班`；`一对多` 在 Payroll 当前规则中映射为 `1对2`。特殊班型、领航和未知值不猜测，保留 source 扩展并进入人工/适配处理。

### grade

`grade` 不进入当前 canonical minimum contract，但两边都从排课事实中产生，且 Payroll 的工资系数强依赖它。因此它应成为 **Shared/Core 的 canonical schedule extension**，而不是 Payroll-owned 私有输入；Shared/Core 只发布标准年级事实，Payroll 仍拥有工资系数和年级工资政策。跨学年、衔接班、领航等无法确认的年级继续保留人工复核，不写进公共主键。

### teacher identity

Dashboard 已禁止用“任课老师”显示名填入 `teacher_id`。Payroll 当前仍以 `teacher` 姓名作为排课、工资记录和 reconciliation 的 key；这属于 `NEEDS_ADAPTER_LATER`，不能直接接入 canonical teacher_id。由于本轮禁止修改 Payroll，不在本轮全量改名或迁移身份表。

### source_record_id

Dashboard 的 API 原始响应有 `ID`，但标准化 `ScheduleRecord` 当前没有保存；Payroll 的 Excel/CSV adapter 也没有稳定来源记录 ID。行号、教师+时间拼接或当前文件 hash 都不能自动升级为记录 ID。进入 Phase 2 共享发布前，这必须是 adapter 的硬门槛；缺失时 fail closed。

## 信息损失审计

### PAYROLL_ONLY_FIELDS

`grade` 的工资系数上下文、`class_name`、`course_name`、`lesson_time` 原文、`duration_text` 原文、`provenance` 单元格证据、工资对账字段 `AA/AC/AD/AE/AF/AV`、人工裁决、批注、续费/退费/兼职/管理绩效。

其中工资字段、人工裁决和工资政策明确归 Payroll；`grade`、课程/班级原文和来源证据属于 schedule extension/provenance，不应塞进 canonical minimum。

### DASHBOARD_ONLY_FIELDS

`expected_students`、`attended_students`、`lesson_hours`、`amount`、Dashboard 的 `snapshot_date`、指标 `measure_type/value`、`manual_month_weeks`、`forecast_snapshots`。这些是 Dashboard 指标或来源扩展，不是 canonical schedule minimum。

### SHARED_FIELDS

教师引用、校区/学科维度、课程来源 ID、上课日期、班级/学生引用、班型、状态、实到、时长、来源和期间/来源追溯。当前多数只是“语义共享”，还不是两边可直接读取的同一字段。

### 能否重建

- 只保存 canonical schedule **不能**重建 Payroll 的全部工资输入：缺少工资表 AA/AC、星级、AE/AF、人工裁决、续费、退费、兼职和管理绩效。方案是 `CanonicalSchedule + PayrollScheduleExtension + Payroll-owned inputs/decisions`。
- 只保存 canonical schedule **也不能**重建 Dashboard 的全部指标输入：缺少 Dashboard 的 expected 学员数、人工月配置、外部教师数/总单科数分母和预排快照。方案是 `CanonicalSchedule + OpsScheduleExtension + metric snapshot/provenance`。

## 未来合并路径（只设计）

1. **Phase 1：两个 repo 独立。** 固定本契约；双方只维护各自 adapter 和脱敏 contract tests。现在不建 shared package、不合并 repo。
2. **Phase 2：canonical 发布边界。** Shared/Core 先发布带 canonical IDs、source_record_id、完整 provenance 的 schedule；Payroll 和 Dashboard 各自消费，不互相调用内部模型。只有身份解析、记录 ID 稳定性和业务状态枚举通过 UAT 后才进入这一阶段。
3. **Phase 3：统一产品外壳 / namespaces。** 只有当两个系统已有稳定 adapter、canonical 发布有实际复用、版本/权限/迁移责任明确时，才评估统一外壳和 `core.* / ops.* / payroll.* / analytics.*` 数据库 namespaces。

当前结论：还不到 monorepo、shared package 或 shared database 的时机，三项均为 `NO`。
