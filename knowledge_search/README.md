    # knowledge_search

    Knowledge search over the JSONL knowledge store, filtered by the caller's data scope.

    **Phase 0 skeleton.** Cloud Run service; locally `docker compose --env-file compose/local.env up` (port 8083).

    Build and test from this folder: `uv run pytest`.

    | Variable | Default | Meaning |
    |---|---|---|
    | `PORT` | `8083` | Port to listen on (Cloud Run sets it) |
| `LOG_LEVEL` | `INFO` | Minimum log level |
