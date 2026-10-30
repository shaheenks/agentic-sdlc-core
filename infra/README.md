# infra

Terraform for GCP. One root module, `gcp/`, deploys one environment per state prefix
(version-01 M7: `dev` in project `sdlc-demo-env01`, region `asia-southeast1`; `staging.*` is kept for later). Driven by `scripts/gcp_deploy.ps1` (Windows PowerShell 5.1 or `pwsh`).
Design, diagrams, IAM/secrets, cost and runbook: [docs/GCP_DEPLOYMENT.md](../docs/GCP_DEPLOYMENT.md).

| File | What |
|---|---|
| `gcp/main.tf` | APIs, Artifact Registry, locals (deterministic `*.run.app` URLs, image names) |
| `gcp/sql.tf` | Cloud SQL PostgreSQL 17 (Enterprise, connector only, no authorized networks), database, admin user |
| `gcp/secrets.tf` | Generated DB passwords + oauth2-proxy cookie secret; Entra secrets and `groups.yaml` from local files |
| `gcp/iam.tf` | One service account per workload (`mcp`, `app`, `jobs`): Cloud SQL client, Vertex AI user, own secrets only; MCP: custom role on the `sdlc-<env>-user-` secret prefix (user connections) |
| `gcp/run.tf` | Cloud Run `sdlc-mcp-<env>`, `sdlc-app-<env>` (oauth2-proxy + agent + CopilotKit chat app sidecars; `/chat/` → app, `/connections/` → MCP), jobs `sdlc-db-setup-<env>`, `sdlc-ingest-<env>` |
| `gcp/sessions.tf` | Agent Engine `sdlc-sessions-<env>`: the agent's conversation store (sessions only, TTL `session_retention_days`; version-01 M8) |
| `gcp/<env>.tfvars`, `gcp/<env>.gcs.tfbackend` | Per-environment values (no tenant IDs) and state location |

First deployment (from the repo root; commit first, the image tag is the commit SHA):

```powershell
.\scripts\gcp_deploy.ps1 -EnvName dev -Step state    # state bucket (once)
.\scripts\gcp_deploy.ps1 -EnvName dev -Step base     # APIs + registry
.\scripts\gcp_deploy.ps1 -EnvName dev -Step images   # build + push (Docker Desktop)
.\scripts\gcp_deploy.ps1 -EnvName dev -Step plan     # review the plan
.\scripts\gcp_deploy.ps1 -EnvName dev -Step apply
.\scripts\gcp_deploy.ps1 -EnvName dev -Step db       # roles, schema, RLS (sdlc-db bootstrap + migrate)
.\scripts\gcp_deploy.ps1 -EnvName dev -Step ingest
.\scripts\gcp_deploy.ps1 -EnvName dev -Step urls     # app URL, MCP URL, OAuth callback
```

Then register the `oauth_callback` output on the `sdlc-client` Entra app (admin action).
Updates: commit, `images`, `plan`, `apply`. Teardown: `terraform destroy` with the same tfvars
(`deletion_protection = false` in `dev.tfvars`).

Public access: the org policy `iam.allowedPolicyMemberDomains` forbids `allUsers`, so the two public
services set `invoker_iam_disabled`; every request is still authenticated by Entra (oauth2-proxy
for the app, token validation in the MCP server). The agent and chat app sidecars bind `0.0.0.0`
(Cloud Run's startup probes do not use loopback), but only oauth2-proxy's port 4180 is exposed, so
they are reachable only through oauth2-proxy.
