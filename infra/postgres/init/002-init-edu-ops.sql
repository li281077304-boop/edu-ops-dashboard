-- Runs after 001-create-metabase-database.sql on a fresh PostgreSQL volume.
-- The migration files are mounted read-only at /migrations by Compose.

\getenv analytics_db_user ANALYTICS_DB_USER

\connect edu_ops
\i /migrations/001_metrics.sql
\i /migrations/002_dashboard_views.sql

REVOKE CONNECT ON DATABASE edu_ops FROM PUBLIC;
GRANT CONNECT ON DATABASE edu_ops TO :"analytics_db_user";
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO :"analytics_db_user";
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM :"analytics_db_user";
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM :"analytics_db_user";
GRANT SELECT ON TABLE dashboard_metric_latest, dashboard_metric_trend
  TO :"analytics_db_user";
