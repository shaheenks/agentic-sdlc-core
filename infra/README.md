# infra

Terraform for GCP. One root module, `gcp/`, deploys one environment per state prefix
(Stage 7a: `staging`). Driven by `scripts/gcp_deploy.ps1` (Windows PowerShell 5.1 or `pwsh`).
Design, diagrams, IAM/secrets, cost and runbook: [docs/GCP_DEPLOYMENT.md](../docs/GCP_DEPLOYMENT.md).

| File | What |
|---|---|
| `gcp/main.tf` | APIs, Artifact Registry, locals (deterministic `*.run.app` URLs, image names) |
| `gcp/sql.tf` | Cloud SQL PostgreSQL 17 (Enterprise, connector only, no authorized networks), database, admin user |
| `gcp/secrets.tf` | Generated DB passwords + oauth2-proxy cookie secret; Entra secrets and `groups.yaml` from local files |
| `gcp/iam.tf` | One service account per workload (`mcp`, `app`, `jobs`): Cloud SQL client, Vertex AI user, own secrets only |
| `gcp/run.tf` | Cloud Run `sdlc-mcp-<env>`, `sdlc-app-<env>` (oauth2-proxy + agent sidecar), jobs `sdlc-db-setup-<env>`, `sdlc-ingest-<env>` |
| `gcp/<env>.tfvars`, `gcp/<env>.gcs.tfbackend` | Per-environment values (no tenant IDs) and state location |

First deployment (from the repo root; commit first, the image tag is the commit SHA):

```powershell
.\scripts\gcp_deploy.ps1 -EnvName staging -Step state    # state bucket (once)
.\scripts\gcp_deploy.ps1 -EnvName staging -Step base     # APIs + registry
.\scripts\gcp_deploy.ps1 -EnvName staging -Step images   # build + push (Docker Desktop)
.\scripts\gcp_deploy.ps1 -EnvName staging -Step plan     # review the plan
.\scripts\gcp_deploy.ps1 -EnvName staging -Step apply
.\scripts\gcp_deploy.ps1 -EnvName staging -Step db       # roles, schema, RLS (sdlc-db bootstrap + migrate)
.\scripts\gcp_deploy.ps1 -EnvName staging -Step ingest
.\scripts\gcp_deploy.ps1 -EnvName staging -Step urls     # app URL, MCP URL, OAuth callback
```

Then register the `oauth_callback` output on the `sdlc-client` Entra app (admin action).
Updates: commit, `images`, `plan`, `apply`. Teardown: `terraform destroy` with the same tfvars
(deletion protection is off for staging only).

Public access: the org policy `iam.allowedPolicyMemberDomains` forbids `allUsers`, so the two public
services set `invoker_iam_disabled`; every request is still authenticated by Entra (oauth2-proxy
for the app, token validation in the MCP server). The agent listens on `127.0.0.1` inside the app
instance and is reachable only through oauth2-proxy.
