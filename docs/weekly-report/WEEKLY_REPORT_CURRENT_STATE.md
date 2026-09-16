# Weekly Report Module — current evidence state

更新时间：2026-09-16

本轮以 2026 年 6 月数学组四个连续周次作为最完整的可重放数据集。原始 WPS/TMS 文件只读解析，手工最终版只作 oracle；没有把最终版数值反写回 source adapter。

已验证：真实资产发现、学生/教师/WPS 读取、TMS 生产读取、template-independent snapshot、4 周 Golden 对账（`UNEXPLAINED_DIFFERENCE=0`）、模板 Excel 生成与重开检查。

未完成：当前日历周没有发现可重放的 raw source；真实 2026-06 对账已确认 `bkh = class_production_ks (KS)` 及 `1v1 + bkh/3`，但依赖人工调整 H/L/Q 分母的平均课时/课次仍缺原始来源；学生变化表与人工最终版的差异仍需业务来源/人工修正账；续费/推荐不是本 P0 自动连接项。以上均保留在 snapshot 的 `warnings` / `unresolved_items` 中。

本轮正式 UAT 合同：`WEEKLY_REPORT_UAT.md` / `WEEKLY_REPORT_UAT.json`。当前目录只是历史资产工作区，不是正式产品归属；正式产品 repo 必须在确认现有 Education Operations SaaS 归属后建立或接入。
