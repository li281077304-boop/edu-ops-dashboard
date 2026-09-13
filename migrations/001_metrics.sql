-- 业务库 schema；Metabase application database 使用独立数据库。
-- 原始学生/老师明细不进入这张表。

CREATE TABLE IF NOT EXISTS metric_values (
    id BIGSERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    campus TEXT NOT NULL,
    subject TEXT NOT NULL,
    metric TEXT NOT NULL,
    measure_type TEXT NOT NULL CHECK (measure_type IN ('actual', 'forecast', 'target')),
    value NUMERIC(18, 6) NOT NULL,
    source_run_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (snapshot_date, period_start, period_end, campus, subject, metric, measure_type)
);

CREATE TABLE IF NOT EXISTS forecast_snapshots (
    id BIGSERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    target_start DATE NOT NULL,
    target_end DATE NOT NULL,
    campus TEXT NOT NULL,
    subject TEXT NOT NULL,
    metric TEXT NOT NULL,
    value NUMERIC(18, 6) NOT NULL,
    source_run_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (snapshot_date, target_start, target_end, campus, subject, metric)
);

CREATE INDEX IF NOT EXISTS idx_metric_values_period
    ON metric_values (period_start, period_end, campus, subject);
