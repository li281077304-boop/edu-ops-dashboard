# Metabase 首版看板定义

这是 P6 的可复现配置说明。Metabase 实例部署后按此定义建立一个手机优先 Dashboard，数据源只选择 `dashboard_metric_latest` 和 `dashboard_metric_trend`。

## 首屏

五张 KPI 卡片，统一筛选器为 `campus`、`subject`：

1. 本周平均课次：`metric = weekly_average_lessons`、`measure_type = actual`
2. 本周平均课时：`metric = weekly_average_hours`、`measure_type = actual`
3. 本周预排课时：`metric = weekly_forecast_hours`、`measure_type = forecast`
4. 人工月平均课时：`metric = monthly_average_hours`、`measure_type = actual`
5. 人工月预排课时：`metric = monthly_forecast_hours`、`measure_type = forecast`

## 趋势

折线图使用 `dashboard_metric_trend`：

- X 轴：`period_start`
- Y 轴：`value`
- 分组：`measure_type`
- 筛选：最近 8 个周期、`campus`、`subject`

不要在 Metabase 表达式里重写周均或人工月算法；所有业务计算由 Python/SQL 产出并测试。
