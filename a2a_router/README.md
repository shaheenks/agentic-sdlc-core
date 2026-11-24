    # a2a_router

    The A2A entry point to user_agent for Gemini Enterprise and later third-party surfaces.

    **Phase 0 skeleton.** Cloud Run service; locally `docker compose --env-file compose/local.env up` (port 8082).

    Build and test from this folder: `uv run pytest`.

    | Variable | Default | Meaning |
    |---|---|---|
    | `PORT` | `8082` | Port to listen on (Cloud Run sets it) |
| `LOG_LEVEL` | `INFO` | Minimum log level |
