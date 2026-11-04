#!/bin/sh
# Runs once, on an empty data directory. Creates the runtime role used by the API, worker and
# scheduler: it owns nothing and is subject to FORCE ROW LEVEL SECURITY (table grants and policies
# come from migration 0002). Migrations run as the owner role (POSTGRES_USER).
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v app_password="$DB_APP_PASSWORD" -v db="$POSTGRES_DB" <<'SQL'
SELECT format('CREATE ROLE wesal_app LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wesal_app') \gexec
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO wesal_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO wesal_app;
SQL
