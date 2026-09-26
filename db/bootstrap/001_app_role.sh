#!/bin/sh
# Runs once on first start of an empty Postgres volume (docker-entrypoint-initdb.d).
# Creates the non-superuser application role; superusers bypass RLS, so the app must never
# connect as one.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v app_user="$SDLC_APP_USER" -v app_password="$SDLC_APP_PASSWORD" <<'EOSQL'
CREATE ROLE :"app_user" LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE :"DBNAME" TO :"app_user";
GRANT USAGE, CREATE ON SCHEMA public TO :"app_user";
EOSQL
