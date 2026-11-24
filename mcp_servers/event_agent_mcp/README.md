    # event_agent_mcp

    The MCP server for scheduled and event-triggered runs, as the system identity (DEC-0007).

    **Phase 0 skeleton.** Cloud Run service; locally `docker compose --env-file compose/local.env up` (port 8081).

    Build and test from this folder: `uv run pytest`.

    | Variable | Default | Meaning |
    |---|---|---|
    | `PORT` | `8081` | Port to listen on (Cloud Run sets it) |
| `LOG_LEVEL` | `INFO` | Minimum log level |
| `STORE_MOUNT_PATH` | - | Mount point of the artifact bucket (a local folder in the `local` profile) |
