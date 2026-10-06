# db/migrations

The resulting schema (tables, RLS, grants, lifecycle) is explained in `docs/DATABASE_SCHEMA.md`.

Numbered SQL migrations (`NNN_name.sql`), applied in order by `sdlc-db migrate` as `sdlc_owner`
(`docker compose run --rm migrate`, or `uv run --env-file .env sdlc-db migrate` on the host).
Each file runs in one transaction and is recorded with its checksum in `sdlc.schema_migrations`;
an applied migration must never be edited: add a new file instead.

- `001_knowledge.sql`: `sources`, `documents`, `chunks` (`embedding vector(768)`, HNSW cosine index),
  RLS `ENABLE` + `FORCE` on each, policies `app_read` (SELECT for `sdlc_app`, filtered by
  `sdlc.allowed_sources()` and `sdlc.max_classification_rank()`) and `ingest_all` (for `sdlc_ingest`).
  Missing RLS context = no rows.

- `002_graph.sql`: `entities` (unique per source + key), `mentions` (entity ↔ chunk), `edges` (with the evidence
  chunk), same RLS as chunks; mentions/edges cascade with their chunk. `extraction_cache` is ingest-only.

Every new data table needs `FORCE ROW LEVEL SECURITY`, a `source_id` + `classification_rank` column,
and policies for both roles, plus rows in `tests/db`.
