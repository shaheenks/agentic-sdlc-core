# db/bootstrap

Init scripts for the Docker Postgres (`pgvector/pgvector:pg17`, published on `127.0.0.1:5432`).
They run automatically, in filename order, the **first** time the `pgdata` volume is created:

- `000_extensions.sql` enables pgvector (as superuser).
- `001_roles.sh` creates the roles (idempotent; passwords from `.env` via compose):
  `sdlc_owner` (owns schema `sdlc` and the tables; runs migrations), `sdlc_app` (read-only, used by
  the MCP server) and `sdlc_ingest` (writes knowledge). None is a superuser or has BYPASSRLS, and
  every data table uses `FORCE ROW LEVEL SECURITY`, so even the owner is filtered.

Tables and RLS policies are migrations (`db/migrations/`, applied by `sdlc-db migrate`).

Re-run init from scratch (destroys local data): `docker compose down -v && docker compose up -d --wait`,
then `docker compose run --rm migrate` and `docker compose run --rm ingest run --all`.
Re-run only the roles script on an existing volume (Git Bash needs `MSYS_NO_PATHCONV=1`):
`MSYS_NO_PATHCONV=1 docker compose exec -T postgres sh /docker-entrypoint-initdb.d/001_roles.sh`.
Verify: `uv run --env-file .env pytest tests/e2e/test_db.py tests/db`.
