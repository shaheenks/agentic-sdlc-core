    # event_gateway

    Receives, verifies, deduplicates and triages events, and starts unattended runs.

    **Phase 0 skeleton.** Cloud Run service; locally `docker compose --env-file compose/local.env up` (port 8084).

    Build and test from this folder: `uv run pytest`.

    | Variable | Default | Meaning |
    |---|---|---|
    | `PORT` | `8084` | Port to listen on (Cloud Run sets it) |
| `LOG_LEVEL` | `INFO` | Minimum log level |
