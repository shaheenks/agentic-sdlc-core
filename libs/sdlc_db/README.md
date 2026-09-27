# sdlc_db

Postgres + pgvector access (Stage 5). The only code that reads or writes knowledge data.

| Module | What it does |
|---|---|
| `connect.py` | `conninfo(role)` from the standard `PG*` env: `app` (`PGUSER`/`PGPASSWORD`, read-only, MCP server), `ingest` (`sdlc_ingest`/`SDLC_INGEST_PASSWORD`), `owner` (`sdlc_owner`/`SDLC_OWNER_PASSWORD`, migrations). |
| `scoped.py` | `scoped(conn, policy)`: opens a transaction and sets the RLS context from an `EffectivePolicy` (`app.allowed_sources`, `app.max_classification_rank`, both `SET LOCAL`). Source IDs are validated before they reach SQL. |
| `knowledge.py` | `search()` (cosine, k ≤ 20, HNSW iterative scan so RLS filtering still fills k), `sync_sources()` (config → `sources` registry, removes sources no longer in config), `document_hashes()`, `replace_document()`, `delete_documents()`. |
| `embedding.py` | `GeminiEmbedder` (model/dims from `platform.yaml` `knowledge.embedding`; RETRIEVAL_DOCUMENT vs RETRIEVAL_QUERY), `HashEmbedder` (deterministic, tests only). |
| `migrate.py`, `cli.py` | `sdlc-db migrate`: applies `db/migrations/NNN_*.sql` in order as `sdlc_owner`, records checksums in `sdlc.schema_migrations`, refuses edited migrations. |

Rules:
- Every read runs inside `scoped()`. Without it, RLS returns no rows (fail closed), even for the table owner
  (`FORCE ROW LEVEL SECURITY`).
- `gemini-embedding-2` embeds **one input per call** (a list is merged into a single embedding), so
  `GeminiEmbedder` calls it per text in a small thread pool and checks the count and dimensions returned.
- psycopg async needs a `SelectorEventLoop` on Windows (the CLIs and tests set it).
