# 架构

```text
校管家 SaaS
  ├─ QueryConsumeTotalPro API（课消汇总补充）
  └─ Playwright UI export（排课明细主兜底）
          ↓
       data/raw
          ↓
   normalize / validate
          ↓
     ScheduleRecord（排课明细）
          ↓
      metrics engine
          ↓
  脱敏后的聚合指标 → PostgreSQL → Metabase → Android
```

采集器、标准化和指标层分离。校管家字段变化时只调整 adapter；课消汇总 API 与排课明细 Excel 各自进入适合的指标支路，不把汇总接口误当成逐节排课明细。

原始学生、老师、课表和课消数据只保存在 Mac 本地。云端只接收聚合结果。Metabase application database 与 `edu_ops` 业务数据库分开。
