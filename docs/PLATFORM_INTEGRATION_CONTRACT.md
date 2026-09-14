# Platform Integration Contract

本文件只固定 Dashboard 与未来教学经营平台、Payroll 之间的跨系统边界，不迁移当前数据库，也不要求两个系统现在共享一套 `ScheduleRecord` 实现。

## 1. Canonical IDs

跨系统交换时，以下字段必须使用稳定 ID：

| 业务对象 | canonical 字段 | 约束 |
|---|---|---|
| 教师 | `teacher_id` | 不得用教师姓名或其他 `display_name` 代替 |
| 校区 | `campus_id` | 展示名称只是标签 |
| 学科 | `subject_id` | 展示名称只是标签；例如 `02-数学` 的编号清洗属于 source adapter |
| 课程/排课记录 | `course_id` / `source_record_id` | 优先使用来源系统稳定记录 ID，不用行号或拼接名称 |

`display_name` 可以用于 UI 和人工核对，但不能成为永久主键。Dashboard 当前 source adapter 在没有真实 `TeacherID/教师ID` 时将 `teacher_id` 留空，不把“任课老师”显示名伪装成 ID。

## 2. Canonical schedule minimum contract

Shared/Core 发布的 canonical schedule 至少包含：

| 字段 | 含义 |
|---|---|
| `source_record_id` | 来源系统的稳定排课记录 ID |
| `lesson_date` | 上课日期 |
| `teacher_id` | canonical 教师 ID |
| `campus_id` | canonical 校区 ID |
| `subject_id` | canonical 学科 ID |
| `student_or_class` | 学生或班级引用，按 `class_type` 解释 |
| `class_type` | 一对一、多人/班课等标准类型 |
| `lesson_status` | 已排、已上课、已取消等标准状态 |
| `attended` | 实到事实；缺失时保持缺失，不猜测 |
| `duration` | 标准时长，单位由平台协议固定为小时 |
| `source` | 来源系统/采集通道 |
| `source_version` | 来源字段或 adapter 版本 |

Payroll 与 Dashboard 可以各自扩展业务字段，但不得为了统一而重写双方的 `ScheduleRecord`。未来由 adapter 将各自内部结构映射到本契约。

### 语义约束（兼容性审计补充）

- `duration` 的 canonical 单位为小时，建议使用定点数；课次、lesson factor 和人数系数不是 duration。
- `attended` 表示实到人数，不是布尔出勤；`0` 与缺失值必须保持可区分。
- `class_type` 和 `lesson_status` 的标准枚举由 Shared/Core 发布；未知班型或状态不得猜测。
- `grade`、`grade_origin`、`grade_reason` 暂不进入 minimum contract，但作为 Shared/Core 的 schedule extension 发布；其中后两者解释年级的来源与判定理由，不得替代 source/provenance。Payroll 继续拥有工资系数和年级工资政策。

## 3. Provenance

任何跨系统发布的事实或聚合结果都应能回溯到：

`source_run_id`、`source_file` / `source_hash`、`snapshot_at`、`period`、`rule_version`、`generated_at`。

Dashboard 当前已保留 `source_run_id`，文件校验器生成 `source_file` 与 `sha256`；当前聚合库尚未迁移为完整 provenance 表。新增代码不得丢弃这些来源信息，也不得把运行时 Cookie、Token 或密码写入 provenance。

## 4. 数据所有权

同一个业务事实只能有一个计算 owner：

| Owner | 负责发布 |
|---|---|
| Shared/Core | `teacher`、`campus`、`subject`、canonical schedule、period、source/provenance |
| Payroll | AA、AC、AD、星级、AE、AF（总课时费）、工资政策、工资人工决策、工资结果 |
| Dashboard | 生产课时、平均课次、计划/预排、趋势、目标、预测、经营 KPI |

Dashboard 将来可以消费 Payroll 发布的 AF / 人工成本，但禁止重新实现工资公式。Payroll 可以消费 canonical schedule，但禁止重新抓取一套同义的 Dashboard 排课数据。

## 5. Future database namespaces

长期规划为：

```text
core.*
ops.*
payroll.*
analytics.*
```

本轮不迁移现有 `public` schema，也不新增与该方向相反的业务表。当前 `metric_values`、`forecast_snapshots` 和两个 Dashboard view 属于临时 analytics 输出边界；未来迁移由 adapter/迁移任务负责，不改变上述 owner。

## 6. Compatibility check

### SAFE_NOW

- `source_run_id` 已在指标和预排快照中透传。
- `snapshot_date` 是预排判断的幂等键组成部分，不覆盖其他快照日期。
- `campus`、`subject` 的当前精确筛选和指标输出可由后续 adapter 映射为 `campus_id`、`subject_id`。
- `dashboard_metric_latest` 与 `dashboard_metric_trend` 只发布聚合结果。

### NEEDS_ADAPTER_LATER

- 当前 `ScheduleRecord.campus`、`ScheduleRecord.subject` 是清洗后的展示维度，不是 canonical `campus_id`、`subject_id`。
- Excel 兜底可能只有教师显示名，因此没有 `teacher_id`；必须由 Core 映射后再对外发布。
- 当前指标库的 `campus`、`subject` 文本列需要在未来迁移时映射到 canonical IDs。
- 当前文件级 `sha256` 与 `retrieved_at` 尚未单独成为跨系统 provenance 表。

### MUST_FIX_NOW

- 不得把教师显示名写入 `teacher_id`；当前 adapter 已改为缺失时 fail closed/留空。
- 新的采集、指标和存储代码不得创建以姓名、校区名称、学科名称或行号为永久主键的字段。
- 维度缺失、目标维度不存在、响应包含非法行、日期缺失或指标合同不合法时必须失败关闭，禁止静默丢弃或猜测。

## 7. Explicit business-rule boundary

赠送课、亲属赠送、排课专用课程目前没有可靠排除字段。Dashboard 不猜测其是否属于生产课时；该项保持 `HUMAN_REQUIRED / BUSINESS_RULE_BLOCKED`，直到业务方提供可验证规则。
