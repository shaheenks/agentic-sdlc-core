# user_agent_mcp

The MCP server for calls made as a user ([DEC-0002](../../spec/decisions/DEC-0002.md),
[component](../../spec/components/user-agent-mcp.md)). Cloud Run service; MCP revision 2026-07-28 over
streamable HTTP, stateless, so any instance serves any request.

Every request to `/mcp` and `/api/*` names its user, as the active configuration's `identity.mode` requires
([DEC-0010](../../spec/decisions/DEC-0010.md)):
- `caller_token`: `X-SDLC-User-Id` and `X-SDLC-User-Email`, sent by sdlc_ui (from the IAP assertion it verified)
  or the agent runtime, with `Authorization: Bearer <Google ID token>` of the caller's service account for this
  server's `PUBLIC_URL`. The account must be listed under `identity.callers`, which names the surface.
- `trusted_header` (local only): the same user headers plus `X-SDLC-Surface`, with no proof.
- `oauth` (off for now): the user's own Google token, issued to a declared OAuth client.

The server:
- identifies the user (`libs/sdlc_identity`) and refuses anything else with 401;
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
| `plan_publish` | `plan-<repo>.md` by pull request into the feature branch on the control repository, as the user, for a design a person merged (DEC-0016) |
| `workspace_build` | Builds and tests a change in the credential-free Code Workspace job, from the repository's archive fetched with the user's connection |
| `implementation_publish` | Commits a built change to `sdlc/<control-id>/<repo>` and opens its pull request into the feature branch, as the user, for a plan a person merged |
| `connection_save` | HTTP API only (`PUT /api/connections/{provider}`): stores a secret, AES-256-GCM encrypted, under `secrets/users/<user ID>/` |

HTTP API for sdlc_ui, same policy and audit: `GET /api/me`, `GET /api/artifacts`, `GET|DELETE /api/artifacts/{name}`,
`GET /api/connections`, `PUT|DELETE /api/connections/{provider}`. Public: `GET /healthz` and
`GET /.well-known/oauth-protected-resource`, which names Google as the authorization server.

Calls can carry `X-SDLC-Run-Id` and `X-SDLC-Step`; they go into the audit record and the artifact lineage.
A team run also carries `X-SDLC-Team`: the policy is then the intersection with that team's grants, and the
knowledge tools read only its sources (DEC-0011). A team the user is not in is refused with 403.

Build and test from this folder: `uv run pytest`. Locally:

```sh
uv run sdlc-config publish --env local --to .data/config --activate   # from the repository root
docker compose --env-file compose/local.env up --build user-agent-mcp
curl -H "X-SDLC-Surface: sdlc_ui" -H "X-SDLC-User-Id: 1001" -H "X-SDLC-User-Email: you@your-domain" \
  http://localhost:8080/api/me
```

The last line works when `config/env/local/identity.yaml` has `mode: trusted_header`, allows your domain and
declares the `sdlc_ui` caller; `users.yaml` gives you your teams.

| Variable | Default | Meaning |
|---|---|---|
| `PORT` | `8080` | Port to listen on (Cloud Run sets it) |
| `LOG_LEVEL` | `INFO` | Minimum log level |
| `SDLC_ENV` | `local` | Environment name; the active bundle must be for this environment |
| `CONFIG_SOURCE` | - (required) | Published bundles: a folder, or `gs://<configuration bucket>[/prefix]` |
| `CONFIG_REFRESH_SECONDS` | `30` | How often the active-version pointer is re-read |
| `STORE_MOUNT_PATH` | - (required) | Mount point of the artifact bucket (a local folder in the `local` profile) |
| `PUBLIC_URL` | `http://localhost:$PORT` | This server's URL: the audience callers' ID tokens must carry, and the protected-resource metadata |
| `SDLC_UI_URL` | - | sdlc_ui's URL; `connection_start` links to `<SDLC_UI_URL>/connections/<provider>` |
| `DATA_ENCRYPTION_KEY` | - | Base64 of 32 bytes, from Secret Manager; without it, secrets cannot be saved |
| `DATA_ENCRYPTION_KEY_VERSION` | `1` | Recorded with each encrypted secret |
| `KNOWLEDGE_SEARCH_URL` | - | Knowledge Search; without it the knowledge tools answer `knowledge_unavailable` |
| `WORKSPACE_MODE` | - | `job` (the Cloud Run job `WORKSPACE_JOB`), `local` (in process, local environment only); unset: `workspace_build` is unavailable |
| `WORKSPACE_JOB` | - | `projects/<p>/locations/<r>/jobs/<sdlc-env>-code-workspace-user` |
| `WORKSPACE_TIMEOUT_SECONDS` | `1200` | The job execution's limit |
| `KNOWLEDGE_AUTH` | `id_token` | Its own ID token from the metadata server; `none` only in the `local` environment |

On Google Cloud (`infra/gcp/user_agent_mcp.tf`) only sdlc_ui's and the agent runtime's service accounts hold its
invoker role; ingress is `all` until sdlc_ui runs in the environment, then internal. The artifact bucket is
mounted per prefix (`/data/store/artifacts/users`, `/data/store/secrets/users`). Cloud Run reserves paths
ending in `z`, so `/healthz` is reachable only by its probes. To call it by hand in development (as one of
`sdlc_ui_testers`):

```sh
URL=$(terraform -chdir=infra/gcp output -raw user_agent_mcp_url)
TOKEN=$(gcloud auth print-identity-token --impersonate-service-account=<sdlc_ui service account> \
  --audiences=$URL --include-email)
curl -H "Authorization: Bearer $TOKEN" -H "X-SDLC-User-Id: <your account ID>" \
  -H "X-SDLC-User-Email: <your email>" $URL/api/me
```
