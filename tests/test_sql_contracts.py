from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_dashboard_views_expose_latest_and_trend_without_business_recalculation() -> None:
    sql = (ROOT / "migrations/002_dashboard_views.sql").read_text(encoding="utf-8")
    assert "CREATE OR REPLACE VIEW dashboard_metric_trend" in sql
    assert "CREATE OR REPLACE VIEW dashboard_metric_latest" in sql
    assert "DISTINCT ON (campus, subject, metric, measure_type)" in sql
    assert "snapshot_date DESC" in sql
    assert "FROM metric_values" in sql


def test_business_reader_grants_only_dashboard_views() -> None:
    sql = (ROOT / "infra/postgres/init/002-init-edu-ops.sql").read_text(encoding="utf-8")
    assert "GRANT CONNECT ON DATABASE edu_ops" in sql
    assert "GRANT USAGE ON SCHEMA public" in sql
    assert "REVOKE ALL ON ALL TABLES IN SCHEMA public" in sql
    assert "GRANT SELECT ON TABLE dashboard_metric_latest, dashboard_metric_trend" in sql
    assert "ANALYTICS_DB_PASS" in (
        ROOT / "infra/postgres/init/001-create-metabase-database.sql"
    ).read_text(encoding="utf-8")
