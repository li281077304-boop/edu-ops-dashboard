-- Runs after 001-create-metabase-database.sql on a fresh PostgreSQL volume.
-- The migration files are mounted read-only at /migrations by Compose.

\connect edu_ops
\i /migrations/001_metrics.sql
\i /migrations/002_dashboard_views.sql
