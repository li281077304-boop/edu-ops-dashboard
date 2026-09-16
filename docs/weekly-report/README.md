# 学科组长周报模块

本模块是 Education Operations SaaS 的 Weekly Report domain adapter，不是
桌面 Excel 脚本。输入端读取 WPS/TMS/CSV 等来源并生成稳定的
`WeeklyReportSnapshot`；Web 页面、API 和 Excel 导出都只消费这个 snapshot。

## 运行

```bash
uv sync --extra dev --extra excel
uv run python apps/weekly-report-server.py
```

打开 `http://127.0.0.1:8797/weekly-report`。机器接口为
`/weekly-report/api`，Excel 导出为 `/weekly-report/export`。

## 当前证据

- 最新可完整重放周次：2026 年 6 月第 4 周（并非当前日历周）。
- 4 周历史 Golden：`UNEXPLAINED_DIFFERENCE = 0`；历史 WPS/TMS 与人工最终版的
  差异保留为 `HISTORICAL_SOURCE_GAP`。
- bkh 已确定为班课生产 KS，单位 KS；平均指标仍因缺少正式调整分母而保持
  `SOURCE_MISSING`，不会静默填 0。
- active roster 由 `teacher_config.py` 的 `ACTIVE_TEACHERS` 通过安全 AST 读取，
  其路径和 SHA-256 写入 snapshot provenance。
- 学生人工修正使用 `RAW_CALCULATED + MANUAL_ADJUSTMENT = FINAL_CONFIRMED`，
  没有调整时显式记录空列表。

更完整的 schema、source map、Golden 和当前 UAT 见本目录下对应文件。
