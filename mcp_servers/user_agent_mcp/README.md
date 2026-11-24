# user_agent_mcp

The MCP server for calls made as a user ([DEC-0002](../../spec/decisions/DEC-0002.md),
[component](../../spec/components/user-agent-mcp.md)). Cloud Run service; MCP revision 2026-07-28 over
streamable HTTP, stateless, so any instance serves any request.

Every request to `/mcp` and `/api/*` needs the user's Google account token, issued to an OAuth client that the
active configuration declares for a surface. The server:
- verifies the token (`libs/sdlc_identity`) and refuses anything else with 401;
- resolves the user's teams and user groups (`libs/sdlc_directory`) and effective policy (`libs/sdlc_policy`) from
  the active bundle, read from `CONFIG_SOURCE` and re-checked every 30 seconds;
- lists and allows only the tools of the surface's tool groups that the user is granted, with per-user and
  per-team rate limits;
- audits every list, call and refusal as `log_type: sdlc_audit`, without argument values.

| Tools | What they do |
|---|---|
| `whoami` | The caller's identity, teams, user groups and effective access |
| `artifact_list`, `artifact_read`, `artifact_save`, `artifact_delete` | The user's own artifacts under `artifacts/users/<user ID>/`, versioned |
| `connection_list`, `connection_start`, `connection_revoke` | The user's connections; `connection_start` returns the link to the secure entry page |
| `connection_save` | HTTP API only (`PUT /api/connections/{provider}`): stores a secret, AES-256-GCM encrypted, under `secrets/users/<user ID>/` |

HTTP API for sdlc_ui, same policy and audit: `GET /api/me`, `GET /api/artifacts`, `GET|DELETE /api/artifacts/{name}`,
`GET /api/connections`, `PUT|DELETE /api/connections/{provider}`. Public: `GET /healthz` and
`GET /.well-known/oauth-protected-resource`, which names Google as the authorization server.

Calls can carry `X-SDLC-Run-Id` and `X-SDLC-Step`; they go into the audit record and the artifact lineage.

Build and test from this folder: `uv run pytest`. Locally:

```sh
uv run sdlc-config publish --env local --to .data/config --activate   # from the repository root
docker compose --env-file compose/local.env up --build user-agent-mcp
curl -H "Authorization: Bearer $(gcloud auth print-access-token)" http://localhost:8080/api/me
```

The last line works when `config/env/local/identity.yaml` declares the gcloud CLI's OAuth client for the
`developer_cli` surface and allows your domain.

| Variable | Default | Meaning |
|---|---|---|
| `PORT` | `8080` | Port to listen on (Cloud Run sets it) |
| `LOG_LEVEL` | `INFO` | Minimum log level |
| `SDLC_ENV` | `local` | Environment name; the active bundle must be for this environment |
| `CONFIG_SOURCE` | - (required) | Published bundles: a folder, or `gs://<configuration bucket>[/prefix]` |
| `CONFIG_REFRESH_SECONDS` | `30` | How often the active-version pointer is re-read |
| `STORE_MOUNT_PATH` | - (required) | Mount point of the artifact bucket (a local folder in the `local` profile) |
| `PUBLIC_URL` | `http://localhost:$PORT` | This server's URL, for the protected-resource metadata |
| `SDLC_UI_URL` | - | sdlc_ui's URL; `connection_start` links to `<SDLC_UI_URL>/connections/<provider>` |
| `DATA_ENCRYPTION_KEY` | - | Base64 of 32 bytes, from Secret Manager; without it, secrets cannot be saved |
| `DATA_ENCRYPTION_KEY_VERSION` | `1` | Recorded with each encrypted secret |
| `GOOGLE_CLOUD_QUOTA_PROJECT` | - | Billing project for the Groups API with user credentials (local runs only) |

On Google Cloud, directory modes `direct` and `transitive` need the service account to hold the Groups Reader
admin role in the Google Admin console.
