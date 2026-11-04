# Secrets and revocation review (version-02 N3)

Review date 2026-11-05, scope as decided in D3 (default scope). What we hold, how it is protected,
how fast access can be cut, what was built, and how to rotate. Environments: local (compose) and
GCP dev; staging/prod follow in version-03.

## 1. What we hold

| Secret | Where (GCP / local) | Read by | Set by |
|---|---|---|---|
| Entra client secret (oauth2-proxy sign-in) | Secret Manager `sdlc-<env>-entra-client-secret` / `.env` | `sdlc-app` (oauth2-proxy) | Terraform from `.env` (value also in state) |
| Entra Graph secret (group overage fallback, optional) | `sdlc-<env>-entra-graph-secret` / `.env` | `sdlc-mcp` | Terraform from `.env` (in state) |
| Postgres role passwords (admin, owner, app, ingest) | `sdlc-<env>-pg-*-password` / `.env` | MCP (app), jobs (all), reconcile (app) | Terraform `random_password` (in state) |
| oauth2-proxy cookie secret | `sdlc-<env>-oauth2-cookie` / `.env` | `sdlc-app` | Terraform `random_password` (in state) |
| Source credentials `{secret: x}` / `{env: X}` | Secret Manager secret `x` / `SDLC_SECRET_X`, `X` | ingest job | by hand (`gcloud secrets versions add`), never in Terraform. **None configured today** |
| Users' PATs (GitHub, Bitbucket, Atlassian) | one secret per user `sdlc-<env>-user-<sha256(oid)[:32]>` / Fernet files on the MCP-only volume | `sdlc-mcp` only (name-prefix IAM condition), reconcile job | the user, on the Connections page |
| Tenant data (groups.yaml, users.yaml, blocked.yaml) | inside config bundles in the config store bucket / git-ignored files | MCP, ingest, reconcile | `gcp_deploy.ps1 -Step config` |

Agents and the chat app hold no secrets beyond the ADC file locally; the agent never gets DB
credentials or PATs (CLAUDE.md "Security rules").

## 2. Threats and controls

| Threat | Control today | Residual risk |
|---|---|---|
| Leaked user PAT from our store | Per-user secret, name hashed, owner `oid` checked on read, MCP-only IAM (name condition); tokens must expire within `max_token_days` (90); never logged (masked repr, audit has no values) | The MCP service account can read every user's secret (by design: it serves them) |
| Stale PATs piling up (expired, revoked, removed connection) | **New: reconcile job** (§3) | Between runs, an expired token is refused at use (`NotConnected`), so staleness is storage only |
| Offboarded / compromised user keeps access | `oid` block list checked on every MCP request (401, audited `blocked`); **new: works on GCP via bundles** (§3); reconcile deletes their PATs | Agent UI still loads for them, but every tool call fails |
| Disabled Entra account | Entra stops issuing tokens; existing access tokens live 60–90 min | See §4 (E3) |
| Secret values in logs / traces / bundles | `SecretValue` masked repr; audit records hash arguments; spans carry no values; bundles keep `${VAR}` unresolved | — |
| Platform secrets in Terraform state | State bucket is private (project IAM) | Anyone with state-bucket read sees DB passwords and the Entra client secret. Prod (version-03 E4): federated credentials instead of a client secret |
| Missing / mistyped secret reference | Fails at ingest time | **New: `sdlc-config validate --check-secrets`** (§3) finds it before deploy |
| Lateral use of the reconcile identity | Own service account: user-secret prefix + list (names/labels only), app DB role, bundle read; no Vertex, no other secrets | List shows all secret names in the project (not values) |

## 3. Built in N3

- **Block list on GCP.** `config/env/<env>/blocked.yaml` travels in the config bundle (test:
  `tests/config/test_bundles.py::test_block_list_travels_in_the_bundle`). Block = add the `oid`,
  commit, `gcp_deploy.ps1 -EnvName dev -Step config`; effective within ~2 minutes (60 s poll + the
  bucket mount's cache); unblock = remove + publish again, or roll back the pointer. Decision:
  `sdlc_web` does **not** check the list itself (agents never read config); the MCP server
  refuses every call, which is the authorization boundary.
- **Reconcile job** (`sdlc_connectors.reconcile`, CLI `sdlc-reconcile-connections`, Cloud Run job
  `sdlc-reconcile-<env>`). Rules: blocked user → delete all their PATs; token expired → remove;
  provider rejected it more than 14 days ago → remove; connection no longer in
  `connections.yaml` → remove. Dry run by default; `--apply` changes and audits each change
  (`connection_change`, `actor: reconcile`). Each removal is decided again under the user's lock
  on a fresh read, so a token reconnected meanwhile survives. No "unused for 90 days" rule:
  expiry already bounds every token to 90 days. Schedule: `reconcile_schedule` (Terraform, off by
  default).
- **`sdlc-config validate --check-secrets`.** Resolves every secret reference in config through
  the configured backend and prints names and outcomes only. Needs cloud access for
  `SDLC_SECRETS_BACKEND=gcp`, so not in CI.

## 4. Revocation latency and E3 (decision)

| Action | Takes effect |
|---|---|
| Block list entry published | ~2 min (MCP); PATs deleted at the next reconcile run |
| User removes a connection | immediately (MCP cache dropped on write) |
| User revokes the PAT at the provider | next use: provider 401 → marked invalid → removed after 14 days |
| Entra account disabled | up to the access-token lifetime (60–90 min) |

**Decision (2026-11-05): no token lifetime policy and no CAE work in version-02.** A shorter
access-token lifetime needs a tenant-wide Entra policy (admin action) and only shortens the
window, while the block list already cuts access in ~2 minutes for the cases that matter
(offboarding, compromise). CAE claims challenges apply to CAE-capable resources; our own API
would have to implement claims challenges end to end (MCP clients included). Revisit for prod
(version-03), together with E4 (federated credentials).

## 5. Rotation procedures

Secrets are read as `latest` at instance start (Cloud Run) or with a 5-minute cache (sources).

| Secret | Steps | Downtime |
|---|---|---|
| Entra client secret | New secret on `sdlc-client` (admin action, confirmed per change) → `.env` → `gcp_deploy.ps1 -Step plan` + `apply` (new secret version) → new `sdlc-app` revision (`gcloud run services update sdlc-app-<env> --region <region> --update-labels rotated=<date>`) → delete the old Entra secret | none if both secrets are valid during the switch |
| Entra Graph secret | as above, revision of `sdlc-mcp-<env>` | groups overage fallback only |
| Postgres passwords | `terraform apply -replace='random_password.db["app"]'` (via `plan`/`apply`), then `-Step db` (bootstrap re-sets role passwords), then new revisions of `sdlc-mcp` and the jobs pick it up at next start | short, between `db` and the new revision |
| oauth2-proxy cookie secret | replace `random_password.cookie`, apply, new `sdlc-app` revision | everyone signs in again |
| Source credential `{secret: x}` | `gcloud secrets versions add x --data-file=-` (value never in a file in the repo), disable the old version; next ingest picks it up (5-min cache; a 401 drops the cache) | none |
| User PATs | the user reconnects on the Connections page (each write keeps the newest two secret versions and destroys older ones) | none |

Locally: change `.env` and `docker compose up -d --force-recreate <service>`.

**Status:** the source-credential path (5-minute cache, `invalidate` after a 401) is covered by
`tests/secrets/test_secrets.py` and used by the git, GCS and Atlassian loaders. None of the
procedures above has been run on GCP yet: the first candidate is the reconcile check in
version-02 §19 R5 (no private source exists, D1).

## 6. Recommendations (not built; version-03)

- Secret Manager **data-access audit logs** (`DATA_READ`) on, to see who read which user secret.
- Federated credentials (E4) so the Entra client secret disappears from `.env` and state.
- Optional CMEK for user secrets.
- Alert on `connection_change` spikes and on `auth_failure` reason `blocked` (log-based metric, N4).
