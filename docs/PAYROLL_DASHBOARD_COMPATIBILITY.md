# Payroll / Dashboard Compatibility Matrix

审计范围：Dashboard `fix/sol-review-1` 基线 `0ca2e74`，以及只读 sibling repo `education-payroll` 的 `night/longrun-20260913 @ 4b09ac5ca55b1857e0f93d91e84533dcd75db586`。本文件不修改 Payroll，也不把两套内部 `ScheduleRecord` 合并。

结论先行：本轮结论为 `ADAPT`。当前 Payroll 的 grade inference、semantic mapping 和 source registry 降低了年级、列识别及文件 provenance 的风险，但两边仍不能直接无损互换。教师身份、校区/学科 ID、来源记录 ID、来源版本和完整 provenance 仍须在未来共享发布边界补齐。

## Current-Payroll delta re-audit

旧审计基线是 `feature/payroll-ui-v1 @ af76369016c7dfd7029b222e2fc2ea29384b907f`；本轮改用当前主线 checkpoint。相对旧基线，当前 Payroll 新增或确认了：

- `ScheduleRecord.grade_origin`、`ScheduleRecord.grade_reason`，用于区分直接来源、人工确认、历史推断和跨学年回调，并解释判定理由。
- `grade_inference.py` 与 `resolve_schedule_grade` 的可审计年级权威顺序；冲突仍返回需要输入，不把猜测写成事实。
- `mapping/semantic.py` 的精确列识别与格式漂移检查，以及 `mapping/schedule.py` 的显式映射兜底。无法唯一识别时会要求确认，不静默猜列。
- `source_registry.py` 的文件 SHA-256、sheet、source type、period 组合身份和 source evidence；`excel/package.py` 复用物理文件 hash 并记录一次解析。
- UI `RunStore` 的 UUID run、period、状态、文件版本和规则/政策版本引用。

这些变化把 `grade` 从“来源不明的潜在阻塞”降为可通过 schedule extension 保留的 `ADAPTER`，并把来源文件识别/列映射风险降为可审计的 `ADAPTER`。它们没有解决 canonical teacher/campus/subject ID 或跨导出稳定 `source_record_id`，所以这些字段仍保留 `BLOCKED`。

状态只使用三种：`DIRECT`、`ADAPTER`、`BLOCKED`。`BLOCKED` 表示当前输入不足以安全映射，不表示可以用显示名或猜测值补齐。

最小 prototype 位于 `src/edu_ops/compatibility.py`，只提供
`Dashboard ScheduleRecord → CanonicalScheduleRecord` 和
`Payroll ScheduleRecord-shaped input → CanonicalScheduleRecord` 两条纯函数路径；它不依赖 Payroll package，也不改变任一系统内部模型。

## 字段级矩阵

| CANONICAL_FIELD | PAYROLL_SOURCE | DASHBOARD_SOURCE | SEMANTIC_MATCH | TYPE_MATCH | LOSSLESS_MAPPING | RISK | ADAPTER_NEEDED |
|---|---|---|---|---|---|---|---|
| `source_record_id` | 当前 `ScheduleRecord` 无字段；Excel adapter 也未产出稳定来源记录 ID；UI resolution 可接受人工 `course_record_id`，但不是导入来源 ID | QueryNew 原始 `ID` 存在，但当前 `ScheduleRecord` 未保留 | 否 | 未知 | `BLOCKED` | 导出行号、拼接字段或人工 resolution ID 不能证明跨版本稳定 | `BLOCKED` |
| `lesson_date` | `lesson_time` 中正则提取 `YYYY-MM-DD`，类型为 `str` | `lesson_date`，类型为 `date` | 是 | 否 | `ADAPTER` | Payroll 缺失/异常日期目前作为空字符串 | `ADAPTER` |
| `teacher_id` | 当前 `ScheduleRecord.teacher`、`PayrollRecord.teacher` 使用姓名字符串；教师提交/访问 UI 另有 `teacher_id`，尚未连接排课记录 | `TeacherID/教师ID`；无 ID 时保持空值 | 否 | 否 | `BLOCKED` | Payroll 排课与工资对账仍以姓名为 key，无法证明 UI teacher_id 就是排课 canonical ID | `BLOCKED` |
| `campus_id` | `ScheduleRecord` 无校区字段 | `campus` 只有清洗后的展示名称 | 否 | 否 | `BLOCKED` | 两边都没有可解析的 canonical 校区 ID | `BLOCKED` |
| `subject_id` | `subject` 是展示学科文本并清理数字前缀 | `subject` 是展示学科文本并清理数字前缀 | 部分 | 否 | `BLOCKED` | 文本相同不等于稳定学科 ID | `BLOCKED` |
| `student_or_class` | `student`、`class_name` 两个展示/溯源字段 | `student_id`，没有 class ID/name 字段 | 部分 | 否 | `ADAPTER` | 班课学生/班级语义不对称 | `ADAPTER` |
| `class_type` | `normalize_class_type`：`1对1`、`1对2`、`小班` | 当前保存原始 `course_type`；prototype 对已知形式做同样归一 | 部分 | 否 | `ADAPTER` | 特殊班型、领航等不可猜测 | `ADAPTER` |
| `lesson_status` | 保存原始 `lesson_status`，工资规则主要筛 `已上课` | 保存原始 `status`，取消规则另行识别 | 是（经标准化） | 是 | `ADAPTER` | `已取消/作废/未上课` 的排除边界需统一枚举 | `ADAPTER` |
| `attended` | `Optional[int]`，缺失为 `None` | `Optional[Decimal]`，来自实到人数；缺失保持 `None` | 是：人数 | 否 | `ADAPTER` | 不能把缺失、0、布尔出勤混为一谈 | `ADAPTER` |
| `duration` | known Excel adapter 读取 `上课时长`，缺列时 evidence 退回 `上课时间`；semantic mapping adapter 当前写入空 `duration_text`，工资侧固定课时规则另行处理 | `lesson_hours: Decimal`，已转为小时 | 部分 | 否 | `ADAPTER` | 两条 Payroll 导入路径语义不同；固定工资课时规则不能冒充 canonical duration | `ADAPTER` |
| `source` | 原始文件路径字符串 | API/Excel source 标签或路径 | 部分 | 是 | `ADAPTER` | 来源系统、通道和文件路径混在同一字符串 | `ADAPTER` |
| `source_version` | 无字段 | 无字段 | 否 | 否 | `BLOCKED` | 不能用 Git SHA 或文件名猜来源 schema 版本 | `BLOCKED` |
| `grade` | `ScheduleRecord.grade`；由 class name、student evidence、course export snapshot 等按 authority order 解析 | `grade` 由 `ShiftGradeName` 读取 | 部分 | 是 | `ADAPTER` | 当前已有可审计来源，但 grade 仍是 schedule extension，特殊年级不能猜测 | `ADAPTER` |
| `grade_origin` | `ScheduleRecord.grade_origin`：例如 `DIRECT_SOURCE`、`HISTORICAL_SCHEDULE`、`MANUAL_CONFIRMATION`、`CLASS_ROLLOVER` | 当前 `ScheduleRecord` 无等价字段 | 否 | 是 | `ADAPTER` | 若只投影 grade 会丢失“事实/推断/人工确认”边界 | `ADAPTER` |
| `grade_reason` | `ScheduleRecord.grade_reason` 保存判定理由 | 当前 `ScheduleRecord` 无等价字段 | 否 | 是 | `ADAPTER` | 丢失解释后无法审计年级覆盖、冲突或跨学年回调 | `ADAPTER` |
| `source_run_id` | UI `RunStore.runs.id` 为 UUID；文件记录保存于 run state | 指标行可选 `source_run_id`；采集运行记录另存 JSONL | 部分 | 是 | `ADAPTER` | Dashboard 目前不是 ScheduleRecord 的必备字段 | `ADAPTER` |
| `source_file` | `RunStore` 保存 path；`SourceEvidence` 保存 source_file | `FileValidation.path`；文件校验器生成路径 | 是 | 否 | `ADAPTER` | 绝对路径不适合跨系统传播 | `ADAPTER` |
| `source_hash` | `RunStore.import_file` 计算 SHA-256 | `FileValidation.sha256` 计算 SHA-256 | 是 | 是 | `ADAPTER` | 两边尚未形成共同 provenance 发布记录 | `ADAPTER` |
| `snapshot_at` | run `created_at` 是任务创建时间，不是源数据读取时间 | `retrieved_at` 是读取时间，`snapshot_date` 是业务快照日 | 部分 | 否 | `ADAPTER` | 不能把业务日和采集时刻互相替代 | `ADAPTER` |
| `period` | `ScheduleRecord.period` 直接保存 `YYYY-MM` | 人工月由配置解析；指标保存 period start/end，记录本身无 period | 部分 | 否 | `ADAPTER` | 自然月与人工月不能混用 | `ADAPTER` |
| `rule_version` | 无统一字段；规则散落在 Skill/Excel/脚本 | 无字段；指标代码版本未写入行 | 否 | 否 | `BLOCKED` | 无法重现某次人工/业务规则版本 | `BLOCKED` |
| `generated_at` | run `created_at` 可作为运行生成时刻 | 数据库 `created_at` 是写库时刻；没有显式生成时刻 | 部分 | 是 | `ADAPTER` | 写库时刻不一定等于指标计算时刻 | `ADAPTER` |

## 重点语义审计

### duration

canonical 约定为“小时数”，类型建议 `Decimal`。Dashboard 的 `Duration` 分钟和“小时/分钟”文本可以转换。当前 Payroll 有两条不同路径：known Excel adapter 有 `上课时长` 时读取它，缺列时只保留 `上课时间` evidence；semantic mapping adapter 当前将 `duration_text` 留空，因为 Payroll 工资侧另有固定课时规则。后者不能提供 canonical duration，未来 adapter 必须要求显式时长证据或明确拒绝发布；绝不能把固定两小时工资规则发布为源数据 duration。不能把课次、lesson factor 或人数系数当作 duration。

### attended

canonical 是“实到人数”，不是布尔值。Dashboard 还保留 expected/attended 的来源对，Payroll 使用 `Optional[int]`；两边都区分 0 与缺失。Dashboard 的 canonical adapter 只读取 `attended_students`，不会用 expected 补齐 attended。

### lesson_status

prototype 统一为 `COMPLETED`、`SCHEDULED`、`CANCELLED`、`VOIDED`。Dashboard 已取消/作废课从经营指标排除；Payroll 当前标准排课记录保存原文，工资规则主要只保留“已上课且实到大于 0”，因此不能宣称两套排除逻辑已经等价，必须经 adapter 和契约测试。

### class_type

`1对1` 映射为 `1对1`；`1对2` 保持多人课，不得误判为一对一；`集体班/6人班/8人班/10人班` 可映射为 `小班`；`一对多` 在 Payroll 当前规则中映射为 `1对2`。特殊班型、领航和未知值不猜测，保留 source 扩展并进入人工/适配处理。

### grade

`grade` 不进入当前 canonical minimum contract，但两边都从排课事实中产生，且 Payroll 的工资系数强依赖它。因此它应成为 **Shared/Core 的 canonical schedule extension**，而不是 Payroll-owned 私有输入；Shared/Core 只发布标准年级事实，Payroll 仍拥有工资系数和年级工资政策。当前 Payroll 的 grade inference 已有权威顺序、历史证据范围和冲突 fail-closed 行为，降低了旧审计的风险，但不能替代 canonical ID。

`grade_origin` 与 `grade_reason` 也属于 schedule extension：前者标明年级来自直接源表、历史排课、人工确认或跨学年规则，后者保存判定理由。它们不属于 `CanonicalProvenance` 的 run/file/time 字段，但必须和 `grade` 一起发布；不能只保存 grade 而丢掉事实与推断的边界。跨学年、衔接班、领航等无法确认的年级继续保留人工复核，不写进公共主键。

### teacher identity

Dashboard 已禁止用“任课老师”显示名填入 `teacher_id`。当前 Payroll 的教师访问/提交边界已经有 `teacher_id`，但 `ScheduleRecord.teacher`、工资记录和 reconciliation 仍以姓名为 key；这属于 `NEEDS_ADAPTER_LATER`，不能直接接入 canonical teacher_id。由于本轮禁止修改 Payroll，不在本轮全量改名或迁移身份表。

### source_record_id

Dashboard 的 API 原始响应有 `ID`，但标准化 `ScheduleRecord` 当前没有保存；当前 Payroll 的 Excel/semantic adapters 也没有稳定来源记录 ID。`SourceRegistry.source_id` 是“文件 hash + sheet + source type + period”的语义来源身份，不是行级课程 ID；UI resolution 的人工 `course_record_id` 也不能回填历史导入的 source ID。行号、教师+时间拼接或当前文件 hash 都不能自动升级为记录 ID。进入 Phase 2 共享发布前，这必须是 adapter 的硬门槛；缺失时 fail closed。

### 当前 provenance / period / version

Payroll 当前 `SourceRecord` 能保存 `file_hash`、`file_name`、`sheet`、`source_type`、`period`、状态和结构化 `source_evidence`，package 层对同一物理文件复用 hash 并记录一次解析；这降低了来源重复解析和文件追溯风险。`RunStore` 以 UUID、period、status、文件 SHA-256 和规则/政策版本引用管理一次运行。它仍不是 canonical schedule 的逐记录 `source_run_id`、`snapshot_at`、`generated_at`、`source_version` 发布模型，因此这些字段继续通过 adapter 补齐，不能用创建时间或 Git SHA 猜测。

当前 grade inference 的 `grade_origin/grade_reason` 是 schedule interpretation metadata；`rule_version` 仍应单独记录推理/映射规则版本。两者不能混为一项，也不能把工资 policy version 当作源数据 schema version。

## 信息损失审计

### PAYROLL_ONLY_FIELDS

`grade_origin`、`grade_reason`、`grade` 的工资系数上下文、`class_name`、`course_name`、`lesson_time` 原文、`duration_text` 原文、`provenance` 单元格证据、工资对账字段 `AA/AC/AD/AE/AF/AV`、人工裁决、批注、续费/退费/兼职/管理绩效。

其中工资字段、人工裁决和工资政策明确归 Payroll；`grade`、`grade_origin`、`grade_reason`、课程/班级原文和来源证据属于 schedule extension/provenance，不应塞进 canonical minimum。

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

## 本轮审计结论

- `PAYROLL_REFERENCE`：`night/longrun-20260913 @ 4b09ac5ca55b1857e0f93d91e84533dcd75db586`
- `REFERENCE_DELTA`：相对 `af76369016c7dfd7029b222e2fc2ea29384b907f`，复核并更新 `grade`、`grade_origin`、`grade_reason`、`duration`、`source_record_id`、`source_version`、`rule_version`、`source/provenance`。
- `DIRECT_FIELDS`：无。当前两边字段名、类型或来源边界都仍需要 canonical adapter 明确处理。
- `ADAPTER_FIELDS`：`lesson_date`、`student_or_class`、`class_type`、`lesson_status`、`attended`、`duration`、`source`、`source_run_id`、`source_file`、`source_hash`、`snapshot_at`、`period`、`generated_at`、`grade`、`grade_origin`、`grade_reason`。
- `BLOCKED_FIELDS`：`source_record_id`、`teacher_id`、`campus_id`、`subject_id`、`source_version`、`rule_version`。缺少稳定来源或身份时必须 fail closed。
- `CANONICAL_CONTRACT_CHANGES`：不修改 minimum contract；补充说明 `grade/grade_origin/grade_reason` 是 schedule extension，且 canonical `duration` 不等于 Payroll 固定课时工资规则。
- `MUST_FIX_NOW`：Dashboard adapter 不得把显示名写入 ID，不得从行号/拼接字段制造 source record ID，不得把固定工资课时发布为 duration；本轮均已保持或覆盖测试。
- `DEFERRED_PHASE2_REQUIREMENTS`：canonical teacher identity mapping、stable source_record_id、campus/subject canonical IDs、canonical class/status enum authority、特殊年级/班型业务映射。
- `HUMAN_REQUIRED`：`NO`。上述项目是 Phase 2 的前置工程条件，不阻塞本轮设计。
- `SHARED_PACKAGE_NOW / MONOREPO_NOW / SHARED_DATABASE_NOW`：`NO / NO / NO`。
