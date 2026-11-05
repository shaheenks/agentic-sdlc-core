# infra

Terraform for GCP. One root module, `gcp/`, deploys one environment per state prefix
(version-01 M7: `dev` in project `sdlc-demo-env01`, region `asia-southeast1`; `staging.*` is kept for later). Driven by `scripts/gcp_deploy.ps1` (Windows PowerShell 5.1 or `pwsh`).
Design, diagrams, IAM/secrets, cost and runbook: [docs/GCP_DEPLOYMENT.md](../docs/GCP_DEPLOYMENT.md).

| File | What |
|---|---|
| `gcp/main.tf` | APIs, Artifact Registry, locals (deterministic `*.run.app` URLs, image names) |
| `gcp/sql.tf` | Cloud SQL PostgreSQL 17 (Enterprise, connector only, no authorized networks), database, admin user |
| `gcp/secrets.tf` | Generated DB passwords + oauth2-proxy cookie secret; Entra secrets from local files; `groups.yaml` / `users.yaml` only without a config store bucket |
| `gcp/storage.tf` | Buckets: config store (config bundles `bundles/<env>/`, source docs `source_docs/<source id>/`; read-only for MCP + ingest) and artifact store (temporary files and agent artefacts, deleted after `artifact_retention_days`) |
| `gcp/iam.tf` | One service account per workload (`mcp`, `app`, `jobs`): Cloud SQL client, Vertex AI user, own secrets only; MCP: custom role on the `sdlc-<env>-user-` secret prefix (user connections) |
| `gcp/run.tf` | Cloud Run `sdlc-mcp-<env>`, `sdlc-app-<env>` (oauth2-proxy + agent + CopilotKit chat app sidecars; `/chat/` → app, `/connections/` → MCP), jobs `sdlc-db-setup-<env>`, `sdlc-ingest-<env>` |
| `gcp/sessions.tf` | Agent Engine `sdlc-sessions-<env>`: the agent's conversation store (sessions only, TTL `session_retention_days`; version-01 M8) |
| `gcp/<env>.tfvars`, `gcp/<env>.gcs.tfbackend` | Per-environment values (no tenant IDs) and state location |

First deployment (from the repo root; commit first, the image tag is the commit SHA):

```powershell
.\scripts\gcp_deploy.ps1 -EnvName dev -Step state    # state bucket (once)
.\scripts\gcp_deploy.ps1 -EnvName dev -Step base     # APIs + registry + config store bucket
.\scripts\gcp_deploy.ps1 -EnvName dev -Step config   # publish the config bundle (before plan)
.\scripts\gcp_deploy.ps1 -EnvName dev -Step images   # build + push (Docker Desktop)
.\scripts\gcp_deploy.ps1 -EnvName dev -Step plan     # review the plan (refuses without an active bundle)
.\scripts\gcp_deploy.ps1 -EnvName dev -Step apply
.\scripts\gcp_deploy.ps1 -EnvName dev -Step db       # roles, schema, RLS (sdlc-db bootstrap + migrate)
.\scripts\gcp_deploy.ps1 -EnvName dev -Step ingest
.\scripts\gcp_deploy.ps1 -EnvName dev -Step urls     # app URL, MCP URL, OAuth callback
```

Then register the `oauth_callback` output on the `sdlc-client` Entra app (admin action).
Code updates: commit, `images`, `plan`, `apply`. Teardown: `terraform destroy` with the same tfvars
(`deletion_protection = false` in `dev.tfvars`).

## Config and source docs in the config store bucket

The MCP service and the ingest job read config from `gs://sdlc-config-store-a7484d8b/bundles/<env>/`
(version-02 N13); the sample sources read `gs://sdlc-config-store-a7484d8b/source_docs/<source id>/` (N14).
Copies are made with your own gcloud account (`gcloud config get-value account`); no service writes the bucket.

**Config** (`config/`, `skills/`, tenant `config/env/<env>/groups.yaml` + `users.yaml`): commit, then publish.
Cloud Run picks up the new version within ~2 minutes; no images or apply needed.

```powershell
.\scripts\gcp_deploy.ps1 -EnvName dev -Step config                          # compile, upload, move `current`
gcloud storage cat gs://sdlc-config-store-a7484d8b/bundles/dev/current       # active version
gcloud storage ls gs://sdlc-config-store-a7484d8b/bundles/dev/               # uploaded versions
.\scripts\gcp_deploy.ps1 -EnvName dev -Step config -ConfigVersion <version>  # rollback: move `current` only
```

Never copy config files into the bucket by hand: a bundle is hash-checked (`manifest.json`), and a hand-edited
one is refused (the services keep the last good version).

**Source docs** (repo copy: `tests/fixtures/sample_sources/`, the test corpus). After changing a document, copy
it again and re-ingest (`-Step ingest` on GCP; `docker compose run --rm ingest run --source <id>` locally):

```powershell
$b = 'gs://sdlc-config-store-a7484d8b/source_docs'
gcloud storage rsync --recursive tests/fixtures/sample_sources/eng-standards      "$b/eng-standards"
gcloud storage rsync --recursive tests/fixtures/sample_sources/payments-api       "$b/payments-code"
gcloud storage rsync --recursive tests/fixtures/sample_sources/payments-incidents "$b/payments-incidents"
gcloud storage ls --recursive "$b/**"                                         # check
```

Add `--delete-unmatched-destination-objects` to `rsync` to also remove documents deleted locally (ingest then
removes them from the knowledge store). `platform-infra` is test-only and is not copied.

Public access: the org policy `iam.allowedPolicyMemberDomains` forbids `allUsers`, so the two public
services set `invoker_iam_disabled`; every request is still authenticated by Entra (oauth2-proxy
for the app, token validation in the MCP server). The agent and chat app sidecars bind `0.0.0.0`
(Cloud Run's startup probes do not use loopback), but only oauth2-proxy's port 4180 is exposed, so
they are reachable only through oauth2-proxy.
