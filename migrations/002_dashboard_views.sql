-- Metabase 只连接这些聚合视图，不接触本地原始明细。

CREATE OR REPLACE VIEW dashboard_metric_trend AS
SELECT
    snapshot_date,
    period_start,
    period_end,
    campus,
    subject,
    metric,
    measure_type,
    value,
    source_run_id
FROM metric_values;

CREATE OR REPLACE VIEW dashboard_metric_latest AS
SELECT DISTINCT ON (campus, subject, metric, measure_type)
    snapshot_date,
    period_start,
    period_end,
    campus,
    subject,
    metric,
    measure_type,
    value,
    source_run_id
FROM metric_values
ORDER BY campus, subject, metric, measure_type, snapshot_date DESC;
