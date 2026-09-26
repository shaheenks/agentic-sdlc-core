# db/bootstrap

Init scripts for the Docker Postgres (`pgvector/pgvector:pg17`, published on `127.0.0.1:5432`).
They run automatically, in filename order, the **first** time the `pgdata` volume is created:

- `000_extensions.sql` enables pgvector (as superuser).
- `001_app_role.sh` creates the non-superuser app role `sdlc_app`. Superusers bypass RLS,
  so the app never connects as `postgres`.

Tables and RLS policies arrive in Stage 5 (`db/migrations/`).

Re-run init from scratch (destroys local data): `docker compose down -v && docker compose up -d --wait`.
Verify: `uv run --env-file .env pytest tests/e2e/test_db.py`.

Note for Stage 5: table owners also bypass RLS unless the table has `FORCE ROW LEVEL SECURITY`.
Create tables with a separate owner/migration role, or enable FORCE on every RLS table.
