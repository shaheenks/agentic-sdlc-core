#!/bin/sh
# Database roles and schema. Idempotent: runs on the first start of an empty volume
# (docker-entrypoint-initdb.d) and can be re-run on an existing one:
#   docker compose exec postgres sh /docker-entrypoint-initdb.d/001_roles.sh
#
#   sdlc_owner  - owns schema `sdlc` and its tables; runs migrations (sdlc-db migrate)
#   sdlc_app    - MCP server: read-only, row-level security always applies
#   sdlc_ingest - ingest service: writes sources/documents/chunks
# None is a superuser or has BYPASSRLS; tables use FORCE ROW LEVEL SECURITY.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v app_user="$SDLC_APP_USER" -v app_password="$SDLC_APP_PASSWORD" \
     -v owner_password="$SDLC_OWNER_PASSWORD" -v ingest_password="$SDLC_INGEST_PASSWORD" <<'EOSQL'
SELECT format('CREATE ROLE sdlc_owner LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS', :'owner_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sdlc_owner') \gexec
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS', :'app_user', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user') \gexec
SELECT format('CREATE ROLE sdlc_ingest LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS', :'ingest_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sdlc_ingest') \gexec

-- keep passwords in sync with .env on re-runs
ALTER ROLE sdlc_owner PASSWORD :'owner_password';
ALTER ROLE :"app_user" PASSWORD :'app_password' NOSUPERUSER NOBYPASSRLS;
ALTER ROLE sdlc_ingest PASSWORD :'ingest_password';

CREATE SCHEMA IF NOT EXISTS sdlc AUTHORIZATION sdlc_owner;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM :"app_user";
GRANT CONNECT ON DATABASE :"DBNAME" TO sdlc_owner, :"app_user", sdlc_ingest;
GRANT USAGE ON SCHEMA sdlc TO :"app_user", sdlc_ingest;
-- pgvector's `vector` type lives in public: usage only, no CREATE there for anyone
GRANT USAGE ON SCHEMA public TO sdlc_owner, :"app_user", sdlc_ingest;
ALTER ROLE :"app_user" SET search_path = sdlc, public;
ALTER ROLE sdlc_ingest SET search_path = sdlc, public;
ALTER ROLE sdlc_owner SET search_path = sdlc, public;
EOSQL
