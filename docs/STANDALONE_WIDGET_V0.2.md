# Standalone Android Widget V0.2

## 本地流程

```text
本地 CSV/XLS/XLSX 排课表
  → 现有 ScheduleRecord 标准化
  → 现有 production_hours / planned_hours / weekly_average_lessons
  → 人工月与当前周汇总
  → Dashboard Data Contract v2
  → widget-data.json
  → Android 离线导入和展示
```

命令：

```bash
uv sync --extra excel
uv run edu-ops-widget --input "/path/to/排课列表.xlsx" --output "/path/to/widget-data.json"
```

省略 `--input` 时只在 Downloads 和 Desktop 中查找最近的 `排课列表_*.xls/.xlsx`。`--as-of YYYY-MM-DD` 可用于明确指定数据截止日期；默认使用运行当天。输出使用临时文件校验后原子替换，且拒绝覆盖输入排课文件。

整个流程只读用户选定的本地文件，不自动登录、下载或启动 HTTP 服务。导出的 JSON 仅包含聚合指标、人工月、来源文件名与 SHA-256，不含教师、学生、单节课程或本机绝对路径。

## 质量门

- 文件必须包含有效记录，日期都必须能解析并落在 `config/manual_months.csv` 中同一个人工月。
- 教师、课程状态、班型/教学形式必须可识别。
- 未取消课程必须有应到人数；已上课记录必须有实到人数。
- 课程状态限定为“已上课”“未上课”“已排”或明确取消/作废状态；未知状态停止生成。
- 完全重复的原始行停止生成，避免重复计入。
- 已上课日期晚于数据截止日时停止生成。
- 取消/作废课单独计数，并从已生产、预排和正常课次数中排除。
- 必需字段未知时停止生成或将确实无法计算的卡片标记为 `unavailable`，不会伪装成 0。

## 16 项指标

| 分组 | 指标 |
|---|---|
| 人工月 | 月度已生产 KS、月度预排 KS、总课次、已上课、未上课、已取消/作废 |
| 当前周 | 已生产 KS、完整自然周预排 KS、已上课、未上课、平均课次/教师 |
| 班型结构 | 一对一已生产 KS、一对一预排 KS、班课已生产 KS、班课预排 KS、教师数 |

“已生产”在已上课记录上调用现有 `production_hours`，并限制在数据截止日及以前；`production_hours` 对未上课行会采用应到人数，因此生产汇总不能直接把未上课记录传入。预排使用现有 `planned_hours`。周平均课次沿用现有 `weekly_average_lessons`，分母是人工月内涉及的去重教师数。

月度总课次等于已上课与未上课课次之和；取消/作废课不混入。普通课程班型按现有课时函数分类：一对一使用现有一对一识别，其余归入班课。生产/计划均使用原有 KS 口径，不把授课小时当 KS。

仅凭排课表无法可靠确认的一对一在读人数、全员在读人数、大周/小周目标、满班率、真实收入和生产金额不在 V0.2 主 Widget 中发布。兼容的 V1 数据迁入 V2 时，只保留 V1 确实包含的月度已生产、月度预排、本周平均课次与教师数；其余字段均明确标记为不可用，不会推算。

## Contract v2

根对象包含：

- `schema_version = 2`
- `dashboard`、`updated_at`
- `period`：人工月范围、周数、数据截止日、当前周范围
- `source`：文件名、SHA-256、格式、记录数、日期覆盖范围
- `cards`：固定 16 项。每项包含 `key`、`label`、`value`、`unit`、`format`、`section`、`availability`、`definition`；不可用时 `value=null` 并提供 `reason`
- `sections`：按 `month`、`week`、`structure` 分组的稳定指标 key 列表

Android 不按 key 重新计算指标。导入先解析并校验完整数据；无效文件不会覆盖旧缓存。成功导入后刷新 Widget，之后无网络时继续显示最近一次成功数据。首次安装且尚无有效数据时提示先导入，不提供伪造经营数字。

小尺寸优先显示月度已生产、月度预排、本周已生产、本周预排、本周平均课次和教师数；中尺寸增加月度课次状态和本周课次；大尺寸按人工月、当前周、班型结构展示完整 16 项。不可用项不拿 0 冒充。
