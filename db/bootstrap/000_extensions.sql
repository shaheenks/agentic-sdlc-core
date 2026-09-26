-- Runs once on first start of an empty Postgres volume (docker-entrypoint-initdb.d), as superuser.
-- Tables and RLS policies arrive in Stage 5.
CREATE EXTENSION IF NOT EXISTS vector;
