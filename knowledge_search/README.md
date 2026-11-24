# knowledge_search

Search over the JSONL knowledge store, filtered by the caller's data scope
([Knowledge Search](../spec/components/knowledge-search.md); FR-KNOW-002, FR-AUTHZ-004, NFR-ARCH-004, DEC-0011).

- `POST /search` `{query, mode: hybrid|vector|keyword, limit, filter: {sources: [...]}}`: chunks with their
  source, link, lines and heading.
- `POST /graph` `{entity | name, depth: 1|2, limit, filter}`: an entity's neighbourhood.
- `POST /status` `{filter}`: the ingest run behind this image, for those sources (FR-KNOW-003).

Every query needs `filter.sources`, the source IDs the MCP server computed for its user, and is answered from
those sources alone; a query without it gets 400 `filter_required`. Only the accounts in `ALLOWED_CALLERS` may
call, with a Google ID token whose audience is `PUBLIC_URL`.

The store is built into the image from `knowledge/` (git-ignored; the ingest pipeline writes it just before
the build). Locally, Docker Compose mounts `.data/knowledge` instead. Build and test from this folder:
`uv run pytest`.

| Variable | Default | Meaning |
|---|---|---|
| `PORT` | `8083` | Port to listen on (Cloud Run sets it) |
| `KNOWLEDGE_PATH` | `/app/knowledge` | The store's folder |
| `PUBLIC_URL` | `http://localhost:$PORT` | This service's URL: the audience callers' ID tokens must carry |
| `ALLOWED_CALLERS` | - (required) | Comma-separated service accounts of the MCP servers |
| `CALLER_AUTH` | `id_token` | `none` skips the caller check, in the `local` environment only |
| `SDLC_ENV` | `local` | Environment name |
| `EMBEDDINGS`, `GOOGLE_CLOUD_PROJECT`, `VERTEX_LOCATION` | `vertex`, -, `europe-west3` | The query embedder; must match the store's model |
| `LOG_LEVEL` | `INFO` | Minimum log level |
