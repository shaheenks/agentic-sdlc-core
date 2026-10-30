# Agentic SDLC — Implementation Plan version-02

Follows [version-01.md](version-01.md) (new sources, AG-UI web app, user connections, GCP dev, M0–M8) and
[version-00.md](version-00.md) (Stages 0–9, local backlog H1–H10). Architecture: [../ARCHITECTURE.md](../ARCHITECTURE.md);
GCP runbook: [../GCP_DEPLOYMENT.md](../GCP_DEPLOYMENT.md).

Version-02 collects everything still open from both earlier plans: what version-01 left pending or deferred
(§10.3, §10.4, §6) and what version-00 left open (Stage 7b operations, Stage 8 surfaces, the Stage 9 backlog, the
enterprise gaps E1–E10). §9 maps every carried-over item to its milestone. Nothing here is built yet; scope and order
are a proposal to confirm milestone by milestone.

## Goals

1. **Real knowledge on GCP dev:** the dev sources ingested on Cloud Run, with credentials in Secret Manager and a schedule.
2. **Connectors proven against live systems:** GitHub, Bitbucket, GCS, Confluence and Jira (Cloud and Data Center), both as
   ingest sources and as user connections; retrieval measured per source type. This closes the version-01 exit gate.
3. **Secrets and revocation reviewed and hardened:** block list on GCP, user-secret lifecycle (reconcile job), secret checks.
4. **Operable GCP:** tracing, scale-out, config bundles with reload, CI deploys, custom hostnames; ready for a staging
   environment.
5. **Product backlog** picked by priority: conversation history in the chat app, Cloud + Data Center side by side, write
   tools (decision), Gemini Enterprise (still deferred until its prerequisites exist).

## Progress

| Milestone | Status | Notes |
|---|---|---|
| N0 — Carry-over checks | ⏳ | version-01 §10.4 checks not yet confirmed on localhost / the tunnel (G1, G2, G5, G7) |
| N1 — Dev sources on GCP + ingest | ⏳ | Needs the list of sources (§1) |
| N2 — Live connector checks + retrieval eval | ⏳ | Needs test instances and tokens (§2, §8) |
| N3 — Block list and secret management review | ⏳ | Review first, then build (§3) |
| N4 — Observability on GCP | ⏳ | Cloud Trace export (§4) |
| N5 — GCP operations (Stage 7b) | ⏳ | Scale-out, bundles + reload, CI deploy, hostnames, staging (§5) |
| N6 — Product backlog | ⏳ | Pick items per priority (§6) |
| Deferred — Gemini Enterprise | ⏸ | Design in version-01 §6; needs an org admin, a workforce pool and licences |

**Next:** N0 (quick, local), then N1 once the dev sources are decided.

## Open decisions

| # | Question | Needed for |
|---|---|---|
| D1 | Which sources does GCP dev get? (keep the sample folders? `sdlc-platform`: https GitHub location or drop it? which GitHub/Bitbucket repos, GCS bucket, Confluence space, Jira project; their secret names) | N1 |
| D2 | Which Atlassian Cloud site replaces the `acme.atlassian.net` placeholder in `config/connections.yaml`? Is a Data Center test instance available? | N2 |
| D3 | Block list and secret management: scope of the review (§3); one user secret per user stays, or move to one per connection / a separate credential service? | N3 |
| D4 | A staging environment in version-02, or dev only? (project, region, hostnames) | N5 |
| D5 | Write tools on behalf of the user (create issue, comment, PR): in version-02 or later? | N6 |

## 1. Dev sources on GCP + ingest (N1)

From version-01 §10.3 and §5.1. Config is baked into the images (`SDLC_CONFIG_WATCH=false`), so every sources change is
`images` + `plan` + `apply` before the `ingest` step. The user runs Terraform and the deploy script.

- Update `config/sources/` for dev (D1). `sdlc-platform` reads this repository's `.git`, which the ingest image does not
  contain: point it at an `https` location with `provider: github` (pinned SHA stays for the eval) or leave it out of dev.
- Remote hosts in `platform.yaml` `knowledge.allowed_hosts` (Confluence attachments also need `api.media.atlassian.com`).
- **Source credentials in Terraform:** one Secret Manager secret per `{secret: name}` reference, with
  `secretAccessor` for the jobs service account only. `{secret: name}` is looked up as the secret id `name` itself
  (no `sdlc-<env>-` prefix): decide whether to keep that or add an env prefix in `sdlc_secrets` (then local `env`
  mapping stays the same). Values are set outside Terraform (no secrets in state), e.g. `gcloud secrets versions add`.
- GCS buckets in `gcs_source_buckets`.
- **Cloud Scheduler** triggering `sdlc-ingest-<env>` per source group (the Source `schedule` field becomes a cron).
- Each new source: persona-matrix `data_rows`, CODEOWNERS rule, `sdlc-config diff` reviewed.
- Gate: ingest succeeds on GCP; per persona, `search_knowledge` / `graph_query` return only readable sources, with
  citations linking to the right file/page/issue.

## 2. Live connector checks + retrieval eval (N2)

Connectors were built and tested against fakes only (version-01 §2, §4.8–4.10). Live checks need the prerequisites in §8.

- **Ingest sources:** one GitHub repo, one Bitbucket repo per edition, one GCS bucket, one Confluence space and one Jira
  project per edition. Check first: Confluence Cloud v1 CQL search (Atlassian is retiring v1 endpoints; fallback = v2
  listing by space + per-page restriction calls), Cloud attachment download redirects, Jira Cloud `search/jql`
  paging, the `security` field with and without issue security, Bitbucket DC links behind a context path.
- **User connections:** Jira and Confluence Cloud (`atlassian` connection, after D2); every Data Center edition (needs
  config entries, version-01 §4.9). Verify the Bitbucket DC "who am I" endpoint (`/plugins/servlet/applinks/whoami`,
  undocumented; fallback = an authenticated REST call that returns the user).
- **PDF OCR (version-00 H10):** built but never checked live; run a source with `spec.ingest.pdf.ocr: gemini`
  (`platform-infra`'s scanned notices) on GCP and check page citations.
- **Retrieval eval:** questions per new source type in `tests/evals/retrieval_questions.yaml` (vector vs hybrid).
- **Remaining AG-UI gate items** (version-01 §7): gate 3 (answers cite Confluence/Jira/GitHub sources by URL; users
  without access never see them); gate 5 Jira part (connect a Jira PAT, a second user whose provider account lacks
  access gets the provider's denial); gate 2 with Antigravity.

## 3. Block list and secret management review (N3)

Review first (D3), then build what the review keeps. Candidates from version-01:

- **Block list on GCP:** today no `blocked.yaml` is mounted on the MCP service. Store it in Secret Manager and mount it
  as a file like `groups.yaml`; decide how it updates without a redeploy (new secret version + reload) and whether the
  agent (`sdlc_web`) should also refuse blocked users before calling the MCP server.
- **Reconcile job** (version-01 §4.7): delete user secrets of blocked users, expired tokens, connections left
  `invalid`, users not seen for 90 days. Note: `max_token_days` (90) already caps every token, so expiry cleanup covers
  most stale connections without tracking "last seen" per call. Cloud Run job with the MCP service account + Cloud
  Scheduler; locally a CLI with `--dry-run`. Audit `connection_change` with actor `reconcile`.
- **`sdlc-config validate --check-secrets`:** every `{secret:}` / `{env:}` reference resolves (exists), values never
  printed; needs cloud access, so not in CI.
- **User secrets:** Secret Manager data-access audit logs on; optional CMEK; re-check the custom role and its name-prefix
  condition; revisit one-secret-per-user vs one-per-connection or a separate credential service (version-01 §9).
- **Global secrets:** rotation procedure (5-minute cache, re-read after 401) written down and tried once.
- **Revocation latency (version-00 E3, still open):** the `oid` block list exists; short token lifetime policy and CAE
  claims challenges do not. Decide whether a token lifetime policy (tenant change, admin-confirmed) is worth it.

## 4. Observability on GCP (N4)

- OTLP export from agent and MCP to **Cloud Trace** (locally Jaeger). Same rules as locally: one agent turn = one trace,
  no prompts, responses, tokens or argument values in spans; audit records keep `trace_id`.
- Log-based views for the audit events (`tool_call`, `auth_failure`, `connection_change`) in Cloud Logging.

## 5. GCP operations, Stage 7b (N5)

From GCP_DEPLOYMENT §10 and version-00 Stage 7:

- **Scale out `sdlc-app`:** conversations are in Agent Engine (version-01 M8); confirm oauth2-proxy cookie sessions are
  enough, then raise `app_max_instances`.
- **Shared rate-limit store** when `sdlc-mcp` runs more than one instance (limits are per instance today).
- **Config bundles on GCS** with a `current` pointer and Pub/Sub reload (compile/activate/rollback exist locally), so
  config changes no longer need new images.
- **CI deploy stages:** build → plan → apply (validate, diff and tests already run on GitHub Actions); the user approves
  applies.
- **Custom hostnames** `<service>-sdlc-<env>.shaheenks.co.in`: CNAME + Google-managed certificate, then drop the
  `*.run.app` exception.
- **Cloud SQL private IP.**
- **Staging** (D4): a second environment with its own tfvars/state/groups, Entra callback, and no dev shortcuts.
- **Enterprise readiness** for staging/prod (version-00 gaps): E4 certificates or federated credentials (Entra trusts
  GCP workload identity) instead of client secrets; E5 Entra apps in Terraform (`azuread`) with a reviewable manifest;
  E6 no Azure CLI pre-authorization outside dev (`entra_setup.ps1 -NoAzCliPreAuth`); a per-environment Entra client
  app; E1 app roles defined in the tenant (code and config support them since Stage 3) before onboarding real users
  with large group claims.
- **Stage 7b gate (version-00):** a config change is promoted by bundle + pointer flip without a redeploy; rollback by
  pointer.

## 6. Product backlog (N6)

- **Chat app:** load conversation history after a reload (`/agents/state`) and a thread list per user (version-01 §3.1
  known limitations).
- **Connections:** several connections per tool so Cloud and Data Center of one product can be offered side by side
  (version-01 §4.9); MCP URL elicitation for "not connected" where the client supports it.
- **Write tools** on behalf of the user (D5): create issue, comment, PR. Each needs policy, UI confirmation (UX, never
  authorization) and its own review; provider content stays untrusted.
- **Surfaces (version-00 Stage 8):** Antigravity OAuth sign-in through the MCP server's protected-resource metadata and
  the pre-registered `sdlc-client` (enterprise path; today it uses an Azure CLI dev token); then the Stage 8 gate (same
  `whoami(explain)` in adk web, the chat app and Antigravity).
- **Sources (version-00 Stage 9):** a `sharepoint` source type; Office documents (docx, xlsx, pptx); chunking by
  definition for more code languages; GitHub App installation tokens (needs a minting step); mirroring native ACLs
  (`access.inherit_from_source: true`) instead of skipping restricted items.
- **Config tooling:** `sdlc-config explain` by UPN (lookup through the Graph fallback; today personas and group aliases).
- **Quality:** ADK evals in CI; retrieval ranking (query-entity extraction, re-ranker) measured on `tests/evals`.
- **Access model:** Entra OBO for downstream calls where a provider supports it; OPA/Cedar if rules outgrow YAML; an
  admin UI over config (still git-backed).

## 7. Deferred: Gemini Enterprise

Unchanged from version-01 §6: WIF with Entra as OIDC provider, the agent on Agent Runtime, Gemini Enterprise OAuth
authorization for the MCP scope, configurable session-state key in `sdlc_auth.adk`. Agent Engine sessions (version-01
M8) are already the store it would use. Picked up when an org admin, a workforce pool and licences are available.

## 8. Prerequisites to arrange

| Needed | For | Who |
|---|---|---|
| The list of dev sources, their URLs and secret names (D1) | N1 | You |
| Read-only tokens: GitHub fine-grained PAT, Bitbucket Cloud repository access token, Bitbucket DC HTTP access token | N1, N2 | Repo owners |
| A GCS bucket with sample documents in `sdlc-demo-env01` (your go-ahead) | N1, N2 | GCP project owner |
| Atlassian Cloud test site (D2) + a Confluence/Jira Data Center instance with PATs enabled | N2 | Atlassian admin |
| Approval for new billable GCP resources (Cloud Scheduler, a staging environment) | N1, N5 | You |
| Entra admin changes (per-environment client, certificates, app roles) | N5 | Entra admin (confirmed per change) |
| GCP organization admin, workforce pool, Gemini Enterprise licences | Deferred | Org admin |

## 9. Carried over

| From | Item | Milestone |
|---|---|---|
| version-01 §10.4 | Exit-gate checks G1, G2, G5, G7 on localhost / the tunnel | N0 |
| version-01 §10.3 | Dev sources + ingest on GCP, source secrets in Terraform, GCS buckets, Cloud Scheduler | N1 |
| version-01 §7, §8, §9 | Live checks of every connector (ingest + user connections, Cloud and DC), retrieval eval per source type, AG-UI gate items 2 (Antigravity), 3 and 5 (Jira) | N2 |
| version-01 §4.9 | Bitbucket DC "who am I" endpoint unverified; DC connections not configured | N2 |
| version-01 §10.3, §4.7 | Block list on GCP, reconcile job, `--check-secrets`, user-secret review | N3 |
| version-01 §10.3 | Cloud Trace export | N4 |
| version-01 §3.1, §4.9, §4.5 | Chat history reload + thread list; Cloud + DC per tool; URL elicitation; write tools | N6 |
| version-01 §6 | Gemini Enterprise (WIF, Agent Runtime, OAuth authorization) | Deferred |
| version-00 H10 | PDF OCR live check | N2 |
| version-00 E3 | Short token lifetimes, CAE claims challenges | N3 |
| version-00 Stage 7b | Config bundles on GCS + Pub/Sub reload, CI promotion, custom hostnames, scale-out, shared rate-limit store, Cloud SQL private IP | N5 |
| version-00 E1, E4, E5, E6 | Tenant app roles, certificates / federated credentials, Entra apps in Terraform, no Azure CLI pre-auth outside dev | N5 |
| version-00 Stage 8 | Antigravity OAuth sign-in (enterprise path); same-policy gate across surfaces | N6 (Gemini Enterprise part: deferred) |
| version-00 Stage 9 | SharePoint source, Office documents, chunking by definition, `inherit_from_source`, OBO, ADK evals in CI, retrieval ranking, OPA/Cedar, admin UI | N6 |
| version-00 Stage 3 | `sdlc-config explain` by UPN | N6 |
| version-00 E9 | Multi-tenant sign-in | Out of scope (unchanged) |
