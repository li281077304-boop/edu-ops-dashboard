-- The official Postgres image runs this once on a fresh volume.
-- The password arrives through psql's variable substitution and is never
-- committed to the repository.

\getenv mb_db_pass MB_DB_PASS

SELECT format('CREATE ROLE metabase LOGIN PASSWORD %L', :'mb_db_pass')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'metabase')\gexec

ALTER ROLE metabase LOGIN PASSWORD :'mb_db_pass';

SELECT 'CREATE DATABASE metabase_app OWNER metabase'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'metabase_app')\gexec

SELECT format('CREATE DATABASE edu_ops OWNER %I', current_user)
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'edu_ops')\gexec
