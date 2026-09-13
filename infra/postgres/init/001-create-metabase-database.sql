-- The official Postgres image runs this once on a fresh volume.
-- The password arrives through psql's variable substitution and is never
-- committed to the repository.

\getenv mb_db_pass MB_DB_PASS
\getenv analytics_db_user ANALYTICS_DB_USER
\getenv analytics_db_pass ANALYTICS_DB_PASS

SELECT format('CREATE ROLE metabase LOGIN PASSWORD %L', :'mb_db_pass')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'metabase')\gexec

ALTER ROLE metabase LOGIN PASSWORD :'mb_db_pass';

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'analytics_db_user', :'analytics_db_pass')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'analytics_db_user')\gexec

ALTER ROLE :"analytics_db_user" LOGIN PASSWORD :'analytics_db_pass';

SELECT 'CREATE DATABASE metabase_app OWNER metabase'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'metabase_app')\gexec

SELECT format('CREATE DATABASE edu_ops OWNER %I', current_user)
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'edu_ops')\gexec
