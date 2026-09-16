# Dashboard Data Contract v1

`Dashboard Data Contract v1` 是 Python Dashboard、HTTP API、离线 `widget-data.json` 和 Android Widget 之间唯一的数据边界。Android 只展示已经计算好的 `cards`，不按 `key` 重算经营指标，也不知道输入来自 Excel、API 还是其他核心系统。

## 结构

```json
{
  "schema_version": 1,
  "data_status": "live",
  "dashboard": {"id": "xc2", "name": "二校经营看板"},
  "updated_at": "2026-09-16T09:00:00+08:00",
  "period": {
    "start": "2026-08-31",
    "end": "2026-09-27",
    "label": "人工月9 · 2026-08-31 ～ 2026-09-27"
  },
  "cards": [
    {"key": "monthly_produced_ks", "label": "月度已生产", "value": "...", "unit": "KS", "format": "number"},
    {"key": "monthly_planned_ks", "label": "月度预排", "value": "...", "unit": "KS", "format": "number"},
    {"key": "one_to_one_weekly_average_ks", "label": "一对一周平均", "value": "...", "unit": "KS / 人 / 周", "format": "number"},
    {"key": "total_weekly_average_ks", "label": "全员周平均", "value": "...", "unit": "KS / 人 / 周", "format": "number"},
    {"key": "average_lessons", "label": "平均课次", "value": "...", "unit": "次 / 教师", "format": "number"},
    {"key": "big_small_week_ks", "label": "大小周课时", "value": "大周 ...\n小周 ...", "unit": "KS", "format": "text"}
  ]
}
```

`data_status` 可为 `live` 或 `sample`。`sample` 只允许出现在 APK 内置示例；成功 API 同步或文件导入后，缓存中的 payload 必须成为 `live` 数据。

## 指标口径

- 月度已生产、月度预排、大小周课时：经营课时统一为 `KS`，不是小时 `H`。
- 一对一周平均：一对一人工月生产 KS ÷ 一对一在读人数 ÷ 人工月周数。
- 全员周平均：全员人工月生产 KS ÷ 全部在读人数 ÷ 人工月周数；不能使用教师人数或一对一人数替代。
- 人工月周数来自人工月配置，例如 `weeks=4`，不得在 Android 或公式中隐式写死。
- 平均课次沿用既有确认口径：本周截至昨日累计课次 ÷ 固定教师数。
- 大周、小周只接受核心数据层已确认的周总生产课时；没有可靠周型来源时发布 `format=unavailable`，不猜测。
- 赠送课、亲属赠送、排课专用课程继续保持 `BUSINESS_RULE_BLOCKED`，不能自动排除或计入。

## 入口与失败语义

- HTTP：`GET /widget-data.json` 与 `GET /api/status` 返回完全相同的 v1 JSON。
- 离线：`--export-json path/widget-data.json` 使用同一份 Python contract 原子写入文件。
- Android API 同步或文件导入前先校验 schema、Dashboard、周期和六卡顺序；校验失败不替换旧缓存。
- Widget 永远先读本地最近成功 payload；没有缓存时才读 APK 内置 sample，不在 Widget 绘制阶段等待网络。

## 版本策略

当前只支持 v1。未来破坏性变更应增加 `schema_version`，并在 Android 发布兼容迁移后再切换；不为旧 Demo 的非正式字段无限兼容。
