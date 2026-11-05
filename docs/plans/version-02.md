# Agentic SDLC — Implementation Plan version-02

Follows [version-01.md](version-01.md) (new sources, AG-UI web app, user connections, GCP dev, M0–M8) and
[version-00.md](version-00.md) (Stages 0–9, local backlog H1–H10). Architecture: [../ARCHITECTURE.md](../ARCHITECTURE.md);
GCP runbook: [../GCP_DEPLOYMENT.md](../GCP_DEPLOYMENT.md).

Version-02 collects everything still open from both earlier plans: what version-01 left pending or deferred
(§10.3, §10.4, §6) and what version-00 left open (Stage 7b operations, Stage 8 surfaces, the Stage 9 backlog, the
enterprise gaps E1–E10). §9 maps every carried-over item to its milestone. N8–N15 were added and built along the way
(see Progress); N0–N7 are still open, ordered in §19.

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
| N0 — Carry-over checks | ✅ Done (2026-11-04) | version-01 G1, G2, G5, G7 passed on localhost / the tunnel (§19 R1) |
| N1 — Dev sources on GCP + ingest | 🔨 Built (2026-11-05); not applied | D1: the current four sources (already ingested on GCP in R2, no secrets needed). Added: Cloud Scheduler for the ingest job (`ingest_schedule`, off by default). Open: set the schedule, `plan` + `apply` (§19 R7) |
| N2 — Live connector checks + retrieval eval | ⏳ Checks C3–C7 open (§19 R8) | GitHub and GCS ingest live on GCP (R2). Atlassian (D2: no site), Data Center and the PDF OCR live check → version-03. Open: GitHub/Bitbucket Cloud user connections on GCP, AG-UI gates 3 and 5 (retrieval eval done 2026-11-05, C7) |
| N3 — Block list and secret management review | 🔨 Built (2026-11-05); not applied | Review: [docs/SECRETS_REVIEW.md](../SECRETS_REVIEW.md). Block list via bundles (tested), reconcile job + CLI, `validate --check-secrets`, rotation procedures, E3 decision (no lifetime policy / CAE now). Open: `images` + `plan` + `apply`, GCP checks (§19 R5) |
| N4 — Observability on GCP | 🔨 Built (2026-11-05); not applied | Cloud Trace exporter for agent (ADK `trace_to_cloud`) and MCP (`SDLC_TRACE_TO_CLOUD`), `cloud_trace = true` in dev.tfvars, audit views as Logs Explorer queries (GCP_DEPLOYMENT §8). Open: `images` + `plan` + `apply`, gate check (§19 R6) |
| N5 — GCP operations (Stage 7b) | ➡️ Moved to version-03 (2026-11-04) | Bundles + reload done by N13; its Stage 7b gate is checked in §19 R2. Scale-out, CI deploy, hostnames, private IP, staging, E1/E4–E6 → version-03 (§5) |
| N6 — Product backlog | ➡️ Moved to version-03 (2026-11-04) | Chat history done by N15; the rest of §6 (incl. write tools) → version-03 |
| N7 — Agent-generated UI (A2UI) + A2A path for Gemini Enterprise | ✅ Spike done (2026-11-05): GO, build in version-03 | Citation cards from the standard catalog without the model (Google's builder, validated); `/chat/` renders them with the CopilotKit 1.79 we have (`a2ui: { injectA2UITool: false }`); A2A needs `google-adk[a2a]` and an `oid`-bound call context (§10 spike findings) |
| N8 — Chat UX | ✅ Built (2026-10-30); answer rendering confirmed by the user | Answer formatting, `/` opens the chat, navbar user + PAT status (§11). Browser checks passed (2026-11-04, §19 R1); deployed and checked on GCP dev (2026-11-05, §19 R2) |
| N9 — Per-source Entra groups | ✅ Built (2026-11-02) | Sources grant by their own Entra group or `everyone: true`; `graph_query` moved to viewer (§12). The real `infra-readers` group → version-03 (create when a source needs its own group) |
| N10 — Direct members by email (users.yaml) | ✅ Built (2026-11-02) | Users added to teams/roles in git-ignored `users.yaml`, matched by oid; `sdlc-config users sync`; GCP secret mount (§13). Local live check passed (2026-11-04); on GCP dev via the config bundle (2026-11-05, §19 R2). 2026-11-05: Przemek added on dev as sdlc-platform developer (oid synced; `users.yaml` now one flow-style line per user); his access check is with the user (§20) |
| N11 — Rename: `user_agent`, `core_mcp` | ✅ Done (2026-11-03); local stack checked | Starter agent and MCP server renamed for the agent-runtime work (§14). Existing chats no longer show (stored per app name). Deployed on GCP dev (2026-11-05, §19 R2) |
| N12 — Team `sdlc-platform` + GitHub source | ✅ Built (2026-11-03) | `platform` → `sdlc-platform`, members from users.yaml only, source = GitHub `agentic-sdlc-core` tracking `main`; git loader partial-clone fix (§15). Re-ingest + removal of `platform-infra` done locally (2026-11-03) and on GCP dev (R2, 2026-11-05); eval paths updated on the branch (pending task 2) |
| N13 — Config from the config store bucket | ✅ Built (2026-11-03); local bundle checked | MCP + ingest read config bundles from `gs://sdlc-config-store-a7484d8b/bundles/<env>/`, pointer polled every 60 s, `-Step config` publishes (§16). Part of N5 (bundles + reload). Deployed on GCP dev; config-only change + rollback checked (2026-11-05, §19 R2) |
| N14 — Sample sources from the config store bucket | ✅ Built (2026-11-03); live dry-run checked | One-time upload of `samples/sources/*` to `gs://sdlc-config-store-a7484d8b/source_docs/<source id>/`; `eng-standards`, `payments-code`, `payments-incidents` are `gcs` sources (§17); repo copy moved to `tests/fixtures/sample_sources/`. Local DB re-ingested; GCP dev ingested (2026-11-05, §19 R2) |
| N15 — Chat history in the CopilotKit app | ✅ Built (2026-11-04); local stack checked | History sidebar: `GET /threads` (agent, per user) lists previous chats, opening one replays its messages from the agent's `/agents/state`; thread in the URL; delete per chat (`DELETE /threads/{id}`, owner only) (§18). Deployed and checked on GCP dev (2026-11-05, §19 R2) |
| Pending — Agent runtimes (user / CI / ops) | 📝 Design only | Workload identity, read + report back; trigger sources not decided (D7, [pending-task.md](pending-task.md)) |
| Deferred — Gemini Enterprise | ⏸ | Design in version-01 §6; needs an org admin, a workforce pool and licences |

**Scope (narrowed 2026-11-04):** version-02 = close out N8–N15 (checks, GCP deploy, merge to `main`), N0, N1, N2
(Cloud editions), N3, N4 and the N7 spike. No new features until R1 and R2 are done.

**Status (2026-11-05): build complete, user checks open.** Everything in scope is built and committed; what is
left is the merge, one GCP deploy and checks, all run by the user: the handover checklist in §20. Version-02 closes
when §20 is ticked; [version-03.md](version-03.md) (draft) then becomes the current plan.

## Open decisions

| # | Question | Needed for |
|---|---|---|
| D1 | Which sources does GCP dev get? **Decided 2026-11-05:** the current four (`eng-standards`, `payments-code`, `payments-incidents` from the config store bucket; `sdlc-platform` from GitHub `main`); no new sources | N1 |
| D2 | Atlassian Cloud site / Data Center instance? **Decided 2026-11-05:** none available; Jira/Confluence live checks move to version-03 (they stay tested against fakes); `connections.yaml` keeps the placeholder | N2 |
| D3 | Block list and secret management review scope? **Decided 2026-11-05:** default scope: one secret per user stays; build the GCP block-list check, reconcile job, `validate --check-secrets`, rotation procedure; token lifetime / CAE as a written decision only | N3 |
| D4 | A staging environment in version-02, or dev only? **Decided 2026-11-04:** dev only; staging in version-03 with N5 | — |
| D5 | Write tools on behalf of the user (create issue, comment, PR)? **Decided 2026-11-04:** version-03 (with N6 and the agent runtimes) | — |
| D6 | Replace CopilotKit with an own chat client (`@ag-ui/client` + `@a2ui/react`)? **Not pursued** (2026-10-30): no Gemini Enterprise benefit (GE has its own UI); it would only remove the Node runtime and its workarounds at the cost of owning a chat UI. Revisit if the CopilotKit runtime becomes a burden | — |
| D7 | Agent runtimes: interactive `user_agent` plus autonomous `ci_agent` / `ops_agent` (own workload identity, read + report back). **Pending** (2026-11-03): trigger sources not decided; design in [pending-task.md](pending-task.md) | later (version-03) |

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

**Preferred path (2026-10-30, §10):** register the agent as an **A2A agent** (Cloud Run) with an **OAuth authorization
against Entra** (`serverSideOauth2`: `clientId`, `clientSecret`, `authorizationUri`, `tokenUri`; scope
`api://<sdlc-mcp>/access_as_user offline_access` in the authorize URI). GE then sends the user's token in
`Authorization: Bearer`, which `sdlc_web`'s middleware already validates, and renders the agent's A2UI natively. No
token in session state, no configurable state key. Sign-in to GE itself still needs WIF with Entra as OIDC provider.

**Alternative:** the version-01 §6 design (agent on Agent Runtime, token in session state under the authorization id).
Agent Engine sessions (version-01 M8) are the store either way.

Still deferred: needs a GE app and licences, an org admin for the workforce pool, and GE's A2A agent registration is
**Preview** (Pre-GA terms). N7 makes the agent ready in the meantime.

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
| A GE app + a new Entra client registration with GE's OAuth redirect URI (for the A2A agent authorization) | Deferred (§7) | Entra admin (confirmed per change) |

## 9. Carried over

| From | Item | Milestone |
|---|---|---|
| version-01 §10.4 | Exit-gate checks G1, G2, G5, G7 on localhost / the tunnel | N0 |
| version-01 §10.3 | Dev sources + ingest on GCP, source secrets in Terraform, GCS buckets, Cloud Scheduler | N1 |
| version-01 §7, §8, §9 | Live checks of every connector (ingest + user connections, Cloud and DC), retrieval eval per source type, AG-UI gate items 2 (Antigravity), 3 and 5 (Jira) | N2 |
| version-01 §4.9 | Bitbucket DC "who am I" endpoint unverified; DC connections not configured | N2 |
| version-01 §10.3, §4.7 | Block list on GCP, reconcile job, `--check-secrets`, user-secret review | N3 |
| version-01 §10.3 | Cloud Trace export | N4 |
| version-01 §3.1, §4.9, §4.5 | ~~Chat history reload + thread list~~ (done: N15, §18); Cloud + DC per tool; URL elicitation; write tools | N6 |
| version-01 §6 | Gemini Enterprise (WIF, Agent Runtime, OAuth authorization) | Deferred |
| version-00 H10 | PDF OCR live check | N2 |
| version-00 E3 | Short token lifetimes, CAE claims challenges | N3 |
| version-00 Stage 7b | Config bundles on GCS + Pub/Sub reload, CI promotion, custom hostnames, scale-out, shared rate-limit store, Cloud SQL private IP | N5 |
| version-00 E1, E4, E5, E6 | Tenant app roles, certificates / federated credentials, Entra apps in Terraform, no Azure CLI pre-auth outside dev | N5 |
| version-00 Stage 8 | Antigravity OAuth sign-in (enterprise path); same-policy gate across surfaces | N6 (Gemini Enterprise part: deferred) |
| version-00 Stage 9 | SharePoint source, Office documents, chunking by definition, `inherit_from_source`, OBO, ADK evals in CI, retrieval ranking, OPA/Cedar, admin UI | N6 |
| version-00 Stage 3 | `sdlc-config explain` by UPN | N6 |
| version-00 E9 | Multi-tenant sign-in | Out of scope (unchanged) |
| version-01 §6 | Gemini Enterprise design, now with the A2A + A2UI path | N7 (agent side), §7 (deferred GE setup) |

## 10. Agent-generated UI (A2UI) and the A2A path for Gemini Enterprise (N7)

Explored and approved 2026-10-30. **Keep CopilotKit; make the agent GE-ready.**

### Findings
- **A2UI** ([a2ui.org](https://a2ui.org/); Google, Apache-2.0, CopilotKit contributes; spec v0.9.1 current, v1.0
  candidate; [`@a2ui/react`](https://github.com/a2ui-project/a2ui) 0.14.0): a declarative JSON format for
  agent-generated UI, limited to a **catalog** of approved components that client and agent both know. The client
  renders it with its own components and validates it; no executable code. **It is not a chat app**: renderers draw
  surfaces only. Its own ADK + AG-UI guide uses `ag_ui_adk` (what we run) with CopilotKit on the client
  (`@copilotkit/a2ui-renderer`) ([guide](https://a2ui.org/guides/a2ui-with-any-agent-framework/),
  [renderers](https://a2ui.org/reference/renderers/), [transports](https://a2ui.org/concepts/transports/),
  [catalogs](https://a2ui.org/concepts/catalogs/)).
- **Gemini Enterprise has its own UI with a built-in A2UI renderer** (standard components, A2UI v0.8 / v0.9, GE
  styling). Custom agents are registered as **A2A agents** (Cloud Run or Agent Runtime); A2UI travels as A2A
  `DataPart` (`application/json+a2ui`); GE sends its catalog per request; widget actions come back as the next turn
  ([register A2UI agents](https://docs.cloud.google.com/gemini/enterprise/docs/a2ui-agents/register-and-manage-an-a2ui-agent),
  [host on Cloud Run](https://docs.cloud.google.com/gemini/enterprise/docs/a2ui-agents/tutorial-host-agent-cloud-run),
  [Google Cloud blog](https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration)).
  Whether GE accepts components outside its own catalog is unclear.
- **GE auth fits our token path:** an A2A agent can carry an OAuth authorization; GE then sends the user's token in
  `Authorization: Bearer` ([register A2A agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-a2a-agent),
  Preview). For `.run.app` URLs GE also sends a Google OIDC token in `X-Serverless-Authorization` (consumed by Cloud
  Run; our services use `invoker_iam_disabled`, Entra stays the gate).
- **For GE the web front end is irrelevant:** neither CopilotKit nor an own chat client runs inside GE. What carries
  over is an **A2A endpoint** on the agent and the agent emitting **A2UI from the standard catalog**; the same A2UI
  renders in GE (A2A) and in `/chat/` (AG-UI + an A2UI renderer). Replacing CopilotKit: D6, not pursued.

### Work
1. **Spike first** (no product code until it passes):
   - how an ADK agent emits A2UI over AG-UI (`ag_ui_adk`) and over A2A from one code path;
   - whether the standard catalog can show our citation cards (title, link, source, lines/pages), the identity panel
     and connected-tool results;
   - an A2UI version accepted by both GE (v0.8 / v0.9) and `@copilotkit/a2ui-renderer`;
   - ADK's A2A server support with our ADK version, and how it fits behind `sdlc_web`'s middleware.
2. **A2UI output (after the spike):** produced **deterministically from MCP tool results** (citations, whoami,
   connected-tool results), never invented by the model for security-relevant data; standard catalog only; links
   `http(s)` only; A2UI user actions are input to the agent, **never authorization** (version-01 §3.2 item 5). The chat
   app renders A2UI with `@copilotkit/a2ui-renderer` (exact pin), replacing the hand-written renderers
   (`ui/copilotkit/components/renderers.tsx`) where the result is equivalent.
3. **A2A endpoint** on the agent service behind the same Entra middleware: user id = token `oid`, token only in the
   request context (never in session state), client state sanitised, one conversation = one session in the existing
   store (SQLite locally, Agent Engine on GCP). Reachable through oauth2-proxy locally; on GCP, how GE reaches it
   (direct to the agent with a Bearer token vs through oauth2-proxy) is decided in the spike.
4. **Tests and gate:** the same `search_knowledge` answer renders as citation cards in `/chat/` (AG-UI) and through a
   local A2A client (A2UI DataPart); the version-01 M5 security tests hold for the A2A endpoint (no token -> 401,
   another user's session refused, client state sanitised, no token in persisted events); CI runs the UI checks.

GE registration itself (OAuth authorization, GE app, Entra client) stays deferred (§7).

### Spike findings (2026-11-05) — verdict: GO, build in version-03

Checked against the installed versions, no product code (a scratch script only):

| Question (Work item 1) | Finding |
|---|---|
| Can citation cards come from the standard catalog, without the model? | **Yes.** `a2ui-agent-sdk` 0.9.0 (already installed through `ag-ui-adk` 0.11) has a typed builder (`a2ui.builder.v0_9`). A citation = `Card` → `Column` → `Text` (title, `h4`), `Text` (source · path · lines, `caption`), `Button` with `action.functionCall` `openUrl(url)`; there is no Link component, `openUrl` is the catalog's way. Built from a `search_knowledge` hit, it serialises to `createSurface` + `updateComponents` (v0.9) and every component validates against the SDK's v0.9 basic-catalog models (an invalid variant is rejected). URLs are checked `http(s)` before building |
| How does `/chat/` render it? | **No upgrade needed.** Our pinned `@copilotkit/react-core` 1.79.0 already ships `@copilotkit/a2ui-renderer` 1.79.0 and `@a2ui/web_core` 0.10.4 (v0.8 and v0.9 processors). Path: a tool result carrying `{"a2ui_operations": [...]}` → the runtime's A2UI middleware (`@ag-ui/a2ui-middleware` 0.0.10, enabled by `new CopilotRuntime({ a2ui: { injectA2UITool: false } })`) → an `a2ui-surface` activity → rendered. With `injectA2UITool: false` and no `schema`, nothing is injected into the model: the middleware only renders A2UI it finds |
| `ag_ui_adk`'s own A2UI support? | **Not for us.** Its `generate_a2ui` tool has a sub-agent **model** write the UI (with a lenient validator). That breaks our rule that security-relevant UI is built deterministically from tool results; we use only the transport (the `a2ui_operations` key) and Google's builder |
| Version for both GE and the chat app | **v0.9.** GE accepts v0.8 / v0.9 (§10 findings); the renderer processes both; the SDK's builder targets v0.9 |
| ADK A2A server | Present in ADK 2.10 (`google.adk.a2a.utils.agent_to_a2a.to_a2a` → a Starlette app) but needs the `google-adk[a2a]` extra (`a2a-sdk`), not installed today. **Security finding:** without an authenticated call context, ADK sets the user id to `A2A_USER_<context_id>`, and the context id comes from the client: our endpoint must build the a2a-sdk call context from the token our middleware verified (`user_name` = token `oid`), never fall back. The user's token for MCP calls must be request-scoped, as on the AG-UI path |

**Build plan (version-03; §10 Work items 2–4 stand, with these specifics):**
1. A `sdlc_agent` helper turns structured MCP results (`search_knowledge` / `graph_query` citations, `whoami`,
   connected-tool results) into v0.9 operations with the builder; an ADK `after_tool_callback` attaches them under
   `a2ui_operations`. Decide during the build whether the model also sees that JSON (token cost, echo risk) or whether
   it travels as a separate event.
2. Runtime: `a2ui: { injectA2UITool: false }` in `ui/copilotkit/lib/runtime.ts`; replace the hand-written citation
   renderers only where the A2UI result is equivalent (the compact chip line from N8 may stay).
3. A2A: add `google-adk[a2a]`, mount `to_a2a(...)` under `sdlc_web` behind `EntraUserBindingMiddleware`, with an
   a2a-sdk context builder that sets the user from the verified `oid`; tests: no token → 401, another user's
   context id → refused, no token in session state.
4. First step of the build: one end-to-end render of a citation card in `/chat/` (local), then the A2A client test.

**Not verified (needs the build or GE):** the end-to-end render in the browser; whether GE renders our cards
(needs a GE app, §7).

## 11. Chat UX (N8) — built 2026-10-30

**Status:** answer rendering is better (checked by the user, 2026-10-30). Still to check: `/` lands in `/chat/`,
the navbar user status, and the same on the tunnel and on GCP after `images` + `plan` + `apply`.

Requested 2026-10-30: chat answers looked unformatted (an extra blank line after every line), the app should open
on the chat after sign-in, and the navbar should show the signed-in user with the state of their PAT connections.

- **Answer formatting** (`ui/copilotkit`, `agents/user_agent`):
  - CopilotKit renders answers as Markdown with Tailwind typography: 1.25em paragraph gaps and a 65ch width cap.
    When the model separates lines with blank lines, every line becomes a paragraph and looks double-spaced.
    `globals.css` tightens paragraphs, lists and headings for assistant messages only and uses the full column.
  - The agent instruction gained answer rules: short answer first, single blank lines between paragraphs only,
    lists / code fences / tables where they help, headings only for long answers, sources by title, no raw JSON.
  - Dark mode: CopilotKit's dark theme follows a `dark` class, our page follows the OS setting; a fixed inline
    script in `app/layout.tsx` sets the class from `prefers-color-scheme` (and follows changes).
- **`/` opens the chat:** `sdlc_web`'s middleware redirects `GET /` to `/chat/` when the chat app is on
  (`SDLC_AGUI_AGENT` set), after the token check. oauth2-proxy returns users to the page they asked for, so signing
  in at the bare URL lands in the chat. adk web stays at `/dev-ui/`.
- **Navbar user status** (`components/UserStatus.tsx`, `lib/status.ts`) on the chat and Connections pages:
  initials + name, one dot per connection (green connected, amber expiring within 14 days / expired / rejected by
  the provider, grey not connected), a panel with each connection's account and expiry, links to Connections and
  Sign out. Refreshes on focus and after a connect/disconnect. Sign out clears the oauth2-proxy cookie; every
  sign-in sends `prompt=select_account` (`OAUTH2_PROXY_PROMPT`, compose + `run.tf`, 2026-11-04), so Entra shows
  the account picker instead of signing the same user straight back in.
  - `GET /me` (agent middleware): `{name, upn}` from the validated token only (no oid, groups or token),
    `Cache-Control: no-store`.
  - PAT status from the existing `GET /connections/` (MCP server; never returns tokens). Connections off (503) or a
    lapsed session (401): that part is hidden.
  - oauth2-proxy API routes gained `me\b` (compose and Terraform), so a lapsed session gets 401, not a login page.
- **Compact search results** (2026-11-04, `components/renderers.tsx`, `lib/results.ts` `documentChips`):
  `search_knowledge` / `graph_query` render one line: the query, the document count and one chip per cited document
  (deduplicated by source + path; title, else file name, cut to 40 characters; `×N` for several hits; http(s) link
  opens in a new tab; tooltip with source, path, lines/pages and "via graph"); at most 6 chips, then `+N`. Small
  chips (11px); clicking the panel expands the full cards with snippets and the graph entities, clicking the line
  collapses them (keyboard: Enter/Space; chip links never toggle). Display only; the agent still cites sources by
  title in its answer. Test: `tests/results.test.ts` (grouping, labels, unsafe links). The `whoami` card uses the
  same compact card (`CompactCard`): "Signed in as Paul · 2 teams · 4 roles · 2 groups", tags on click.
- **Layout and readability** (2026-11-04, UI only): app name "SDLC Assistant"; the messages and the input use three
  quarters of the chat panel between the history sidebar and the artifacts panel, centred (`--cpk-container-3xl: 75%`
  on `.chat`, full width below 900px; CopilotKit capped it at 48rem); answers at 15.5px / 1.7 line height, inline code as a soft chip without the typography plugin's literal
  backticks. Our colour tokens are now `--sdlc-*`: CopilotKit's stylesheet defines `--muted` and `--accent` (light
  background colours), which made our muted text near-white inside the chat.
- **Connections page, compact** (2026-11-04, `app/connections/page.tsx`): one row per connection (name, provider chip,
  status chip: Connected / Expires in Nd / Expired / Token rejected / Not connected, from `lib/status.ts` `statusChip`;
  account and expiry below), Connect/Replace opens the token form inline (fields side by side), the provider's token
  instructions are a collapsible "How to create this token" inside it, Disconnect asks inline (with the reminder to
  revoke at the provider). A short overview stays visible under the heading. The chat page's navbar no longer links to Connections;
  the user menu's "Manage connections" does. Same API calls and headers as before.
- **Artifacts panel (placeholder)** (`components/ArtifactsPanel.tsx`): a right-hand panel with an empty state for
  files from the artifacts library; "Artifacts" in the navbar shows/hides it (remembered per browser), hidden below
  1100px. No data source yet: the library is [pending-task.md](pending-task.md) task 3.
- **Tests:** `tests/web/test_app.py` (`/me` fields and 401; `/` redirect only with the chat app on, still behind
  sign-in), `ui/copilotkit/tests/status.test.ts` (parsing, states, no token passthrough); typecheck and build.
- **To check (user):** local `docker compose up -d --build --wait`, then in the browser on localhost and the tunnel:
  `/` lands in `/chat/`, answers read normally (light and dark OS theme), the navbar shows your name and connection
  dots, connecting/disconnecting updates them. GCP: `images` + `plan` + `apply` (the API route change is in
  `run.tf`).

## 12. Per-source Entra groups (N9) — built 2026-11-02

**Why:** team membership comes from one Entra group per team, but readers of a source are often not a team. Each
source should be readable by its own Entra group, or by everyone, and `graph_query` should only walk those sources.

**As built:**
- `Source.access` takes `teams`, `roles`, `groups` (group aliases, e.g. one Entra group per source) and, new,
  `everyone: true` (schema, `SourceDef.access_everyone`, resolver reason `everyone <- sources/<id>.yaml#access/everyone`).
  Group grants already existed; they need no team.
- `graph_query` moved from `developer` to `viewer` (`eng-all`), so a source-group member without a team can call it.
  Not `eng-all → developer`: that would hand out `review_code`/`generate_tests` without the teams' repo limits.
- Classification is unchanged: the role ceiling still applies (a source group grants the source, not clearance).
- RLS was already per source (`documents`, `chunks`, `entities`, `mentions`, `edges`); graph joins by key happen at
  query time over RLS-visible rows only. No migration.
- Examples: `eng-standards` → `everyone: true`; `platform-infra` adds `groups: [infra-readers]`. Persona
  `infra-reader` (eng-all + infra-readers, no team) in the matrix; DB test `test_graph_query_for_a_source_group_member`.
- The git-ignored `config/env/{local,dev,staging}/groups.yaml` got an `infra-readers` placeholder ID that matches no
  group (fail closed), so config still validates.

**Open:**
- Create the `infra-readers` Entra group (admin action, needs confirmation), put its object ID in the git-ignored
  `groups.yaml` files, add a test user, then check `whoami(explain=true)` and `graph_query` on localhost and the tunnel.
- Many per-source groups raise the chance of group-claim overage: the Graph fallback (`identity.groups.overage_fallback`)
  covers it; for enterprise tenants, emit only "groups assigned to the application" to keep tokens small.

## 13. Direct members by email (N10) — built 2026-11-02

**Why:** the tenant has no strict Entra group per team or role, so group-based membership can't say who is in a team.
Admins need to add users directly, by their Entra email, to teams (with team roles) and to global roles.

**As built:**
- `config/env/<env>/users.yaml` (kind `UserMap`, `usermap.schema.json`, optional, git-ignored; `users.yaml.example`
  committed): `<alias>: { email, oid, teams: {<team>: [roles]}, roles: [...] }`. Who is in a team is tenant data (per
  env, like Entra group membership); what a team or role can do stays in committed config.
- Matching is on `oid` only (`UserMap.alias_for`); emails are never compared with token claims (they can change or be
  reused). An entry without an `oid` is "pending": validated, reported by `sdlc-config validate`, grants nothing.
- The loader turns entries into ordinary team membership entries and role bindings for `user:<alias>` (rules
  `env/<env>/users.yaml#users/<alias>/teams/<team>` and `.../roles`), so the resolver keeps one path; unknown teams or
  roles, duplicate emails or oids fail validation. `resolve(..., user=)`, `PolicyCache` keyed by the alias too.
  Team `membership` may now be empty (members only from users.yaml).
- MCP: `whoami` returns `user`; audit records carry `user_alias`; admin `config_explain(user=)` and `config_info`
  counts users/pending.
- CLI: `sdlc-config users sync --env <env> [--write] [--check]` (read-only `az ad user show`, prints the az account;
  `--write` saves oids, keeping the header comment only; `--check` reports renamed/deleted accounts);
  `explain --user <alias>`; personas take `user:`; `diff` copies the worktree users.yaml into revisions that know the kind.
- GCP: optional `users_yaml_path` (set by `gcp_deploy.ps1` when `config/env/<env>/users.yaml` exists) → secret
  `sdlc-<env>-users-yaml`, mounted into the MCP service only at `/app/config-users/` (Cloud Run: one secret per
  folder; `config/env/<env>/` already holds groups.yaml) with `SDLC_USERS_FILE` (loader path override; the file
  keeps its usual name in rules and bundles; `compile` ignores the override). `.dockerignore` keeps users.yaml out
  of images.
- Tests: `tests/config/test_users_config.py` (load, validation, resolution, pending, sync with a stubbed az),
  personas `direct-payments-dev`, `direct-viewer`, `pending-user` in the matrix, MCP tests (`whoami` by oid; the email
  claim alone grants nothing).

**Open:**
- GCP dev: run `gcp_deploy.ps1 -EnvName dev -Step plan` then `apply` with `config/env/dev/users.yaml` in place.
- Live check on localhost and the tunnel: a test user with no sdlc groups listed in `users.yaml` sees their team in
  `whoami(explain=true)`.

## 14. Rename: `user_agent` and `core_mcp` — done 2026-11-03

The starter agent and MCP server are renamed for the agent-runtime work ([pending-task.md](pending-task.md)):

| Before | After |
|---|---|
| `agents/bootstrap` (ADK app `bootstrap`, agent `sdlc_bootstrap`, package `sdlc-agent-bootstrap`) | `agents/user_agent` (app and agent `user_agent`, package `sdlc-user-agent`) |
| `mcp_servers/bootstrap` (package `sdlc_mcp_bootstrap`, command `sdlc-mcp-bootstrap`) | `mcp_servers/core_mcp` (`sdlc_core_mcp`, `sdlc-core-mcp`) |
| compose services `mcp-bootstrap`, `agent-bootstrap` | `core-mcp`, `user-agent` |
| images `mcp-bootstrap`, `agent-bootstrap` (Artifact Registry) | `core-mcp`, `user-agent` |
| `tools.yaml` server `bootstrap` | `core-mcp` |
| `SDLC_AGUI_AGENT=bootstrap` (compose, Terraform) | `user_agent` |

Unchanged: `ingest/bootstrap`, `db/bootstrap`, `sdlc-db bootstrap`, Cloud Run service names (`sdlc-mcp-<env>`,
`sdlc-app-<env>`), hostnames, OTel names of other services. `tests/evals/retrieval_questions.yaml` keeps the old paths:
they cite the pinned `sdlc-platform` corpus commit. version-00/01 plans keep the old names (history).

**Effects:** conversations are stored per ADK app name, so existing chats (local SQLite volume, Agent Engine on GCP)
no longer show after the rename. GCP: the next deploy needs `images` (new image names) then `plan` + `apply`; the old
images stay in Artifact Registry until deleted. Local: `docker compose up -d --build --wait --remove-orphans`.

## 15. Team `sdlc-platform` and its GitHub source (N12) — built 2026-11-03

**Why:** reorganise around one real team first. The example `platform` team becomes `sdlc-platform`, whose code lives
in the public GitHub repository https://github.com/shaheenks/agentic-sdlc-core. `payments` stays as the example team.

**As built (decisions 2026-11-03):**
- `config/teams/platform.yaml` → `teams/sdlc-platform.yaml`, `skills/teams/platform/` → `skills/teams/sdlc-platform/`
  (add-on `infra-change-review` and team instructions kept; instructions now name the repository). Roles unchanged
  (viewer, developer, lead, admin). **Members only from `users.yaml`** (`membership: []`), e.g.
  `teams: { sdlc-platform: [lead] }`; `platform-admins` stays the global admin binding.
- Tool limits: `review_code` / `generate_tests` `repo in [agentic-sdlc-core]` (was `platform-infra`, `platform-ci`).
- Sources: `sdlc-platform` = `https://github.com/shaheenks/agentic-sdlc-core.git`, `provider: github`, **`ref: main`
  (tracked)**, no credentials (public); `github.com` added to `knowledge.allowed_hosts`. `eng-standards` kept (owner
  sdlc-platform). `platform-infra` removed from config (its sample folder stays for tests); the N9 `infra-readers`
  alias and its placeholders are removed (the N9 open item about that group is obsolete).
- **Git loader fix** (found by the first live GitHub run): remote clones used `--filter=blob:none`, and `ls-tree -l` /
  `cat-file --batch` then fetched every file lazily, one request each (over 2 minutes, then GitHub hung up). Clones
  and fetches now use `--filter=blob:limit=<MAX_FILE_BYTES>` (all ingestible text in one pack), sizes come from one
  `cat-file --batch-check` (no lazy fetch on git >= 2.44), PDFs above the limit are fetched in one explicit call
  (token only on network calls, `--no-write-fetch-head`), and caches cloned with another filter are re-cloned. A dry
  run reads the repository (181 files, 1012 chunks) in about 6 s.
- Tests: the fixture (`tests/support/config.py`) adds group members (`platform-devs` → developer) and a local
  `platform-infra` source to its copy of sdlc-platform, so group-based tests keep a second team;
  `tests/config/test_repo_teams.py` pins the real config; partial-clone tests in `tests/ingest/test_remote_git.py`.

**Effects and open items:**
- The retrieval eval's `sdlc-platform:` questions now follow `main` (non-deterministic by choice); GitHub `main` is
  still at version-01, so the questions match it until version-02 is merged (then update the paths, e.g. `core_mcp`).
- `sdlc-config diff` against commits before this change fails locally (they reference the removed `infra-readers`
  alias); later revisions diff normally.
- Add the team's members to `config/env/<env>/users.yaml` and run `sdlc-config users sync --env <env> --write`.
- Re-ingest and cleanup are deferred until all sources are fixed: [pending-task.md](pending-task.md) task 2 (the DB
  still holds the old local `sdlc-platform` copy and unreadable `platform-infra` rows).

## 16. Config from the config store bucket (N13) — built 2026-11-03

**Why:** on GCP, config was baked into the images, so every config change needed new images and an apply. Cloud Run
now reads config from the `sdlc-config-store-a7484d8b` bucket. This is the bundle half of N5 (Stage 7b).

**As built (decisions 2026-11-03: bundles, MCP + ingest, poll the pointer):**
- Format: the existing config bundles (`sdlc-config compile`: immutable, hash-verified, config + skills + tenant
  `groups.yaml` / `users.yaml`) under `gs://<bucket>/bundles/<env>/<version>/` with a `current` pointer.
- Terraform (`run.tf`, when `config_store_bucket` is set): the MCP service and the ingest job mount
  `bundles/<env>/` read-only (Cloud Storage volume, `only-dir`, GEN2 execution environment) at
  `/app/config-bundles`, `SDLC_CONFIG_BUNDLES` set; the `groups.yaml` / `users.yaml` secret mounts and
  `SDLC_USERS_FILE` are dropped in that mode (the users.yaml secret is no longer created); MCP service account gets
  `objectViewer` on the bucket (`storage.tf`).
- Reload: `ConfigStore.start_polling` reads `current` every `SDLC_CONFIG_POLL_SECONDS` (60) and reloads on change
  (verified; broken pointer or bundle = keep the last good version, `last_error` set); `start_updates()` chooses
  polling for bundles, file watching for a folder. `load_bundle` ignores `SDLC_USERS_FILE`.
- Ingest: `load_config` reads a bundle or a folder; relative source locations resolve against `SDLC_SOURCES_ROOT`
  (`/app` on GCP) for any `local_folder` source. Since N14 (§17) the sample sources are `gcs` and the image no
  longer carries `samples/`.
- Deploy: `gcp_deploy.ps1 -Step config` compiles (refuses uncommitted changes), uploads the bundle, then moves
  `current`; `-ConfigVersion <v>` rolls back. `base` also creates the bucket; `plan` refuses to run without an
  active bundle. Checked locally: a `dev` bundle loads for the MCP and ingest views, and a dry-run ingest of
  `eng-standards` reads its samples from outside the bundle.
- Tests (`tests/config/test_bundles.py`): polling follows the pointer and keeps a broken one out, startup mode
  selection, the users-file override ignored, ingest from a bundle.

**Open:**
- GCP: `base` (bucket), `config`, `images` (new code), `plan`, `apply`; then check `config_info` (version) and a
  config change via `-Step config` only. The Terraform has not been planned yet: check `mount_options` /
  `execution_environment` in the plan output.
- Pick-up time is up to ~2 minutes (poll + the Cloud Storage mount's metadata cache); Pub/Sub notification and
  publishing from CI stay in N5.

## 17. Sample sources from the config store bucket (N14) — built 2026-11-03

The sample corpus moved out of the repo's runtime path into the config store bucket (one-time move). The artifact
store was not used: it deletes objects after 7 days, keeps no versions and is writable by the agent.

**As built:**
- Upload (once, by the owner's gcloud account): `samples/sources/<folder>` → `gs://sdlc-config-store-a7484d8b/source_docs/<source id>/`
  for `eng-standards`, `payments-code` (from `payments-api/`) and `payments-incidents` (17 files). `platform-infra`
  (test-only since N12) was not uploaded.
- `config/sources/{eng-standards,payments-code,payments-incidents}.yaml`: `type: gcs`, `location:
  gs://sdlc-config-store-a7484d8b/source_docs/<id>/`; include/exclude, classification and access unchanged. Item paths
  are relative to the prefix, so document paths are the same as before.
- Read access: the ingest job's service account already has `objectViewer` on the bucket (storage.tf); locally the
  ingest reads with gcloud ADC (compose mounts it). No `allowed_hosts` change (the gcs loader has a fixed endpoint).
- The ingest image no longer copies `samples/`, and compose no longer mounts it. The repo copy moved to
  `tests/fixtures/sample_sources/` (test corpus; `samples/` is gone): `tests/support/config.py` (`use_sample_folders`)
  points the three sources back to it, so CI needs no GCS. `tests/config/test_repo_teams.py` pins the bucket locations.
- Checked: a live dry run read all three sources from the bucket (6 / 9 / 2 files, 11 / 18 / 6 chunks, the same as
  from the folders); unit and DB tests pass.

**Open:**
- GCP `-Step ingest` after the next `images` + `apply` (local DB re-ingested 2026-11-03, [pending-task.md](pending-task.md)
  task 2).
- Changing a sample document: edit it in `tests/fixtures/sample_sources/` and upload it again (its README).
- The bucket name is in the source config (sources are not per environment): local and GCP dev read the same objects.

## 18. Chat history in the CopilotKit app (N15) — built 2026-11-04

Users could reopen earlier conversations only in the ADK dev UI. The chat app now has the same: a history sidebar
backed by the agent's per-user session store (the one the dev UI reads). Nothing is stored in the chat app.

**As built:**
- Agent: `GET /threads` (`libs/sdlc_web/src/sdlc_web/threads.py`, mounted with `/agui`) lists the caller's sessions
  (`current_oid()` from the validated token; a client `user_id` is ignored), newest first, at most 30:
  `{threadId, title, updatedAt}`. `threadId` = ag_ui_adk's thread key in session state, or the session id for
  sessions started in the dev UI (ag_ui_adk opens those too, so the history is shared). `title` = the first user
  message (whitespace collapsed, 60 characters); state, tool calls and results are never returned. Sessions without a
  user message or stamped by another app are skipped. Titles are cached per (user, session) in the process; a store
  error answers 503 without details.
- Opening a thread: `<CopilotChat threadId>` connects to it; `PassThroughAgentRunner.connect` (`ui/copilotkit/lib/runner.ts`)
  posts `{threadId}` to the agent's `/agents/state` with the forwarded user token only, cleans the messages
  (`historyMessages`: user/assistant/tool, nulls dropped) and replays them as RUN_STARTED, MESSAGES_SNAPSHOT,
  RUN_FINISHED. No token, a bad thread id or an unreadable history opens an empty thread. The runner still stores
  nothing and does not implement CopilotKit's local thread endpoints.
- Runs send only the latest turn (`messageFilter={latestTurn}`): the agent already holds the conversation, so replayed
  history (with ids ag_ui_adk did not record) is never taken as new input.
- UI: `components/ThreadList.tsx` ("New chat", the list, refreshed on load, focus and after each run); the open thread
  is in the URL (`/chat/?thread=<id>`, validated), so reload and bookmarks reopen it. Hidden below 760 px.
- oauth2-proxy: `threads` added to `OAUTH2_PROXY_API_ROUTES` (compose + `run.tf`): an expired session gets 401, not
  a login redirect.
- Not changed: `use_thread_id_as_session_id` stays off (session ids are engine-wide on Agent Engine; the thread key
  in session state already maps threads); retention (7 days) still deletes old chats.
- **Delete a chat** (2026-11-04): `DELETE /threads/{threadId}` (agent, `sdlc_web.threads`) hard-deletes one of the
  caller's conversations (session + events) from the store. The thread is resolved with ag_ui_adk's own lookup
  (`resolve_existing_session`, scoped to the caller's oid), so missing, another user's and another app's threads all
  answer 404. Requires `X-SDLC-Request: 1` (403 without: a cross-site page cannot send it without a CORS preflight);
  no token = 401. Clears ag_ui_adk's in-process thread -> session mapping and the title cache; logs `conversation
  deleted` with oid and thread id (no content). Store errors answer 503. UI: a trash button per sidebar row (on
  hover/focus; always visible on touch), an inline "Delete this chat?" with Delete/Cancel; the row goes at once and
  the list reloads; a refusal shows an error; deleting the open chat starts a new one. No undo (Agent Engine has no
  trash). Dev-UI sessions can be deleted too (and the dev UI's own delete still works on the same store).
- Tests: `tests/web/test_agui.py` (sign-in required, only the caller's threads even with a forged `user_id`, newest
  first, titles cut, a listed thread opens with its history; delete by the owner, 404 for another user and a missing
  thread, 401/403 without token/header, the same thread id starts over, a dev-UI session deleted on a shared SQLite
  store); `ui/copilotkit/tests/threads.test.ts` (parsing, URL ids, latest turn, history cleaning, delete request) and
  `runtime.test.ts` (replay as the same user only; another or no token gets nothing).

**Open:**
- GCP: `images` (agent + chat app) and `plan` + `apply` (oauth2-proxy routes); check the list, reopening and
  deleting a chat on Agent Engine sessions (one listing + one read per new session).
- Later, if wanted: rename chats, "delete all my chats", search across chats, paging beyond 30.

## 19. Plan for the remaining work (2026-11-04)

Everything still open in version-02, in the order to do it. Built milestones (N8–N15) are complete in code; what is
left for them is checks and the GCP deploy, gathered in R1 and R2. Who: **you** = the user (browser checks, Terraform
and `gcp_deploy.ps1`, decisions, admin actions); **Claude** = code, config and docs.

**Corrections to earlier sections:**
- §1 "config is baked into the images": no longer true after N13. On GCP, a sources change is `-Step config` (bundle
  + pointer), then `-Step ingest`; `images` only for code changes.
- §3 "Block list on GCP": bundles load `config/env/<env>/blocked.yaml` like `users.yaml`, so a block can be published
  with `-Step config` and applies within one poll (60 s). Left for N3: confirm this on GCP, and decide whether
  `sdlc_web` refuses blocked users too.
- §5 "Config bundles on GCS + Pub/Sub reload": done by N13 with polling instead of Pub/Sub; the Stage 7b gate is
  checked in R2.
- §6 "Chat app: history and thread list": done (N15).

### Order

| # | Step | Covers | Waits for | Who |
|---|---|---|---|---|
| R1 | Local checks of built work | N0, N8, N10 | nothing | you (Claude prepares the checklist) |
| R2 | GCP dev catch-up deploy + checks | N8, N10, N11, N13, N14, N15; pending task 2 step 5 | R1 (commit first) | you |
| R3 | Merge version-02 to `main`, fix eval paths | pending task 2 step 6 | R2 | you + Claude |
| R4 | Decisions round | D1–D3, artifacts (pending task 3), `infra-readers` group (D4, D5 decided) | — | you |
| R5 | N3 security review, then build | N3, E3 | D3 (the review can start now) | Claude, then you on GCP |
| R6 | N4 observability on GCP | N4 | nothing | Claude, then you on GCP |
| R7 | N1 dev sources on GCP | N1 | D1, tokens (§8) | Claude, then you on GCP |
| R8 | N2 live connector checks + eval (Cloud editions) | N2, H10 | D2, R7, tokens (§8) | you + Claude |
| R9 | N7 A2UI spike | N7 | nothing (spike only) | Claude |
| ~~R10~~ | ~~N5 GCP operations~~ → version-03 | N5, E1, E4–E6 | — | — |
| ~~R11~~ | ~~N6 backlog~~ → version-03 | N6, D5 | — | — |

R5, R6 and R9 depend neither on each other nor on outside people, so they can run while R4's decisions and R7's
prerequisites are being arranged.

### R1 — Local checks of built work (checklist)
Run by you; tick each box here, then mark N0, N8, N10 (and N15's local part) done in Progress. Test users: the
payments developer, the platform/`users.yaml` member, the admin and your own account (no sdlc groups); UPNs stay
out of the repo. Use a private window per user.

**Setup**
- [x] `docker compose up -d --build --wait` (and `docker compose --profile tunnel up -d --wait` for the tunnel).
      Done 2026-11-04 at `2b3e8f8`: all services healthy; L and T redirect to Entra with their own callback; the MCP
      endpoint answers 401 without a token on localhost and the tunnel.
- [x] `uv run --env-file .env sdlc-config validate --env local` passes (2026-11-04).
- [x] Paths: **L** = `http://localhost:4180`, **T** = `https://app-sdlc-dev.shaheenks.co.in`.

**N0 — version-01 gates** (§10.4 of version-01)
- [x] G1 (L, T): the payments developer signs in; `/chat/` and `/dev-ui/` both load.
- [x] G2 (L): "who am I?" in `/chat/` and in `/dev-ui/` list the same teams, roles and tools. Compare the two
      `tools_list` audit records: `docker compose logs core-mcp | Select-String '"event":"tools_list"'`.
- [x] G5 (L): `/dev-ui/` → the session → State shows no token key.
- [x] G7 (L): a connection whose token expires within 14 days shows the warning under the tool result and
      "Expires in Nd" on the Connections page. (Set a short expiry when creating the PAT, or skip if none is at hand.)

**N8 — chat UX** (L and T)
- [x] `/` lands in `/chat/` after sign-in; signing out and in again returns to the page you asked for.
- [x] Answers read normally (lists, code blocks, no blank line after every sentence) in the light and dark OS theme.
- [x] Navbar shows your name and one dot per connection; connecting / disconnecting on the Connections page updates
      them after a reload.
- [x] A `search_knowledge` answer shows one line with document chips; clicking expands the cards, chip links open in
      a new tab.
- [x] Below 1100 px the artifacts panel is hidden; "Artifacts" in the navbar toggles it (empty state only).

**N10 — direct members** (L)
- [x] The `users.yaml` member (sdlc-platform, lead) asks "who am I? explain": team `sdlc-platform` appears with the rule
      `env/local/users.yaml#users/<alias>/teams/sdlc-platform`.
- [x] An account with no sdlc groups and not in `users.yaml` sees only `signed-in` (ping, whoami): checked with a
      no-groups test user (2 tools visible, 14 hidden; `get_agent_context` denied). Your own account is no longer such
      an account: it is in the Entra group `sdlc-payments-leads` and resolves as payments lead (14 tools), as configured.
- [ ] (skipped: covered by the users.yaml member above) Optional strict check: add your own account to `users.yaml` (`teams: {sdlc-platform: [viewer]}`), run
      `uv run sdlc-config users sync --env local --write`, wait for the reload, and check that you now see the team.
      Remove the entry afterwards.

**N15 — chat history** (L, quick re-check after the delete feature)
- [x] The sidebar lists earlier chats; opening one replays it; reload keeps the open chat (`?thread=` in the URL).
- [x] Deleting a chat removes it from the list and it does not come back after a reload.
- [x] A second user (private window) does not see the first user's chats; opening the first user's `?thread=` URL
      gives an empty chat.

**Gate:** every box ticked (or a skipped item written down with the reason); N0 → ✅, the "Open: …browser…" parts
of N8 and N10 closed.

**Result (2026-11-04): passed** at `2b3e8f8`, on localhost and the tunnel. Checked by the user in the browser; audit
cross-check: the payments developer's `tools_list` records are identical across four sessions (`/chat/` and `/dev-ui/`,
14 tools); every `tool_call` matched the caller's roles; the no-groups user got 2 tools and a denied
`get_agent_context`. Finding: the owner's own account had gained `sdlc-payments-leads` in Entra since the test-user
notes were written, so it no longer serves as the "no groups" persona (use a no-groups test user instead).

### R2 — GCP dev catch-up deploy
One run covers every "Open: GCP ..." note of N8, N10, N11, N13, N14 and N15 (runbook: docs/GCP_DEPLOYMENT.md):
`base` (config store bucket) → `config` → `images` (`core-mcp`, `user-agent`, chat app; new names after N11) → `plan`
→ `apply` (with `config/env/dev/users.yaml` in place) → `db` → `ingest` → `urls`. Before `plan`: review the bucket
mount (`mount_options`) in the Terraform, which has not been planned yet (§16).
- Checks: `config_info` shows the published version; a config-only change via `-Step config` takes effect without a
  redeploy and rolls back with `-ConfigVersion` (Stage 7b gate); `ingest` reads the three `gcs` sources and removes
  `platform-infra`; chat history lists and reopens chats; navbar and `/` as in R1; a `users.yaml` member sees their
  team. The old `mcp-bootstrap` / `agent-bootstrap` images can be deleted afterwards.
- Gate: all checks pass on GCP dev; N8, N10, N11, N13, N14, N15 marked fully done.

**Result (2026-11-05): passed** (images `6b319ea`, config `7dfebddda4b6-2979036f3aa0`, then a `users.yaml`-only
bundle and rollback), checked by the user. Finding: a no-groups user's `whoami(explain)` listed `eng-standards`
(`everyone: true`, public) as readable although `signed-in` has no knowledge tool; the audit showed no data read
(only `whoami`; `get_agent_context` denied). Fixed in the explain view: `data.readable` now needs a granted source
within the ceiling AND a `data_scoped` tool; otherwise `data.note` says the grant cannot be used (policy unchanged).
Needs the next `images` + `plan` + `apply` on GCP.

### R3 — Merge to `main`
Merge `version-02` into GitHub `main`, then update the repo paths in `tests/evals/retrieval_questions.yaml`
(`core_mcp`, `user_agent`), re-ingest `sdlc-platform` and run `SDLC_EVAL=1 ... pytest tests/evals`. Closes pending
task 2.

### R4 — Decisions round
| Decision | Unblocks | Suggested default |
|---|---|---|
| D1 dev sources | R7 | **Decided 2026-11-05:** the current four |
| D2 Atlassian site | R8 | **Decided 2026-11-05:** none; Atlassian → version-03 |
| D3 security review scope | R5 | **Decided 2026-11-05:** default scope |
| D4 staging in version-02? | — | **Decided 2026-11-04:** dev only; staging in version-03 |
| D5 write tools now or later? | — | **Decided 2026-11-04:** version-03, with the agent runtimes |
| Artifacts ([pending-task.md](pending-task.md) task 3) in version-02? | — | **Decided 2026-11-05:** version-03 |
| `infra-readers` Entra group (admin action) | N9 live check | Create when a real per-source group is needed |

### R5 — N3 security review (§3)
Write the review first (one page: threats, current controls, gaps, what to build), then build what it keeps:
`sdlc-config validate --check-secrets`; the reconcile job (CLI with `--dry-run`, then a Cloud Run job + Scheduler);
block list on GCP via bundles; global secret rotation tried once; a decision on token lifetime / CAE (E3).
Gate: review accepted; each kept item has tests and a GCP check.

**Built 2026-11-05** ([docs/SECRETS_REVIEW.md](../SECRETS_REVIEW.md)):
- Review: inventory, threats/controls, revocation latency, rotation table; **E3 decision:** no token lifetime policy
  and no CAE in version-02 (the block list cuts access in ~2 min); revisit with E4 for prod.
- Block list on GCP = config bundle (`tests/config/test_bundles.py::test_block_list_travels_in_the_bundle`); `sdlc_web`
  does not check it (agents never read config; the MCP server refuses every call).
- Reconcile: `sdlc_connectors.reconcile` (rules: blocked → delete all; expired; rejected > 14 days; connection removed
  from config), store `scan()` for memory/file/GCP (list by label, owner checked against the name),
  `ConnectionService.prune` (decided again under the user's lock), CLI `sdlc-reconcile-connections [--apply|--dry-run]`,
  audit `connection_change` + `actor: reconcile`. Terraform: job `sdlc-reconcile-<env>`, service account
  `sdlc-<env>-reconcile` (user-secret prefix role + list-only role), `reconcile_schedule` (schedules.tf). Local dry run
  against the real file store: 1 user, 0 changes. Tests: `tests/connectors/test_reconcile.py`.
- `sdlc-config validate --check-secrets` (`tests/config/test_check_secrets.py`); dev: "no secret references in config".

**Your steps (GCP):**
1. Commit is done; `-Step images`, then in `infra/gcp/dev.tfvars` optionally `reconcile_schedule = "30 3 * * *"`
   (and R7's `ingest_schedule`), then `-Step plan`. Expect: new SA `sdlc-dev-reconcile` (+ `sdlc-dev-scheduler` with a
   schedule), two custom roles, the reconcile job, Cloud Scheduler API/jobs if scheduled, new MCP revision. No
   destroys.
2. `-Step apply`, then a dry run: `gcloud run jobs execute sdlc-reconcile-dev --region asia-southeast1
   --args=--dry-run --wait` and read its log (`gcloud logging read 'resource.labels.job_name="sdlc-reconcile-dev"'
   --limit 20`). Expected: the users with a connection, 0 unreadable.
3. Block-list check: add a test user (e.g. the no-groups user) to `config/env/dev/blocked.yaml`, `-Step config`;
   within ~2 min their chat tools fail (401, audit `auth_failure` reason `blocked`); then remove and publish again.
4. Optional: connect a PAT with an expiry of tomorrow as a test user, wait a day (or run on the day after), run the job
   without `--args` override and check the connection is gone and audited.

### R6 — N4 observability (§4)
OTLP export to Cloud Trace from agent and MCP (same span rules as with Jaeger); log-based views for `tool_call`,
`auth_failure`, `connection_change`. Gate: one agent turn = one trace in Cloud Trace with no prompts, tokens or
argument values; audit records link to it by `trace_id`.

**Built 2026-11-05:**
- MCP: `telemetry.setup_tracing` picks Google's Cloud Trace exporter (`opentelemetry-exporter-gcp-trace`) when
  `SDLC_TRACE_TO_CLOUD=true` (project from `GOOGLE_CLOUD_PROJECT`; fails at startup without it), else OTLP as before
  (test: `tests/mcp/test_telemetry.py::test_cloud_trace_exporter_selection`).
- Agent: `sdlc_web` passes ADK's `trace_to_cloud` (same exporter; ADK's `otel_to_cloud`, which also exports logs
  and metrics, stays off).
- Terraform: `cloud_trace` (default false; **dev.tfvars: true**) adds `SDLC_TRACE_TO_CLOUD` to the MCP and agent
  containers and `roles/cloudtrace.agent` to their service accounts; `cloudtrace.googleapis.com` is enabled with the
  other APIs. Cost: the first 2.5 M spans per month are free.
- Audit views: Logs Explorer queries in docs/GCP_DEPLOYMENT.md §8 "Audit views" (denied calls, rate limited, auth
  failures, connection changes incl. reconcile, per user / conversation / trace). Log-based metrics and alerts: version-03.

**Your steps (GCP, same `images` + `plan` + `apply` as R5):** expect `roles/cloudtrace.agent` for
`sdlc-dev-mcp` / `sdlc-dev-app`, the API, new revisions with `SDLC_TRACE_TO_CLOUD=true`. Then ask one question in
`/chat/` that searches knowledge, open Trace explorer (last 15 min, service `sdlc-user-agent`), check that the trace
holds agent, MCP and SQL spans with no prompt text or argument values, and that
`jsonPayload.trace_id="<that trace id>"` in Logs Explorer finds the turn's audit records.

### R7 — N1 dev sources on GCP (§1)
After D1: `config/sources/` for dev, `allowed_hosts`, one Secret Manager secret per `{secret:}` reference (values set
outside Terraform; decide on an env prefix), `gcs_source_buckets`, Cloud Scheduler per source group (billable: needs
your go-ahead), persona-matrix `data_rows` + CODEOWNERS rule per source. Gate as in §1.

**D1 = the current four sources (2026-11-05).** They are configured, have matrix rows and CODEOWNERS rules, need no
secrets (`sdlc-platform` is a public GitHub repo; GCS through the jobs service account) and were ingested and checked
per persona on GCP in R2, which meets §1's gate. Left: the schedule. Built: `ingest_schedule` (schedules.tf; Cloud
Scheduler job `sdlc-ingest-<env>` → the ingest job, as `sdlc-<env>-scheduler`, Cloud Run Invoker on that job only;
off by default). The `{secret:}` env-prefix question is moot until a private source exists (version-03).
**Your step:** set `ingest_schedule = "0 2 * * *"` (or another cron, `schedule_time_zone` default UTC) in
`dev.tfvars`; this enables the Cloud Scheduler API and creates one scheduler job (billable beyond the free tier of
3 jobs per billing account: with reconcile that is 2). `plan` + `apply` together with R5; check the next morning that
`gcloud run jobs executions list --job sdlc-ingest-dev --region asia-southeast1` shows a scheduled run.

### R8 — N2 live connector checks, Cloud editions (§2)
Ingest and user-connection checks for GitHub, Bitbucket Cloud, GCS, Confluence Cloud and Jira Cloud; PDF OCR live
(H10; needs a source with scanned PDFs now that `platform-infra` is gone); retrieval eval per source type; AG-UI gate
items 3 and 5. Moved to version-03: every Data Center edition (incl. the Bitbucket DC "who am I" endpoint) and
Antigravity in gate 2. Gate: version-01 exit gate closed for Cloud editions.

**Scope after D1/D2 (2026-11-05):** no Atlassian site → Confluence/Jira live checks and AG-UI gate 5's Jira part move
to version-03. No source with scanned PDFs → the H10 OCR live check moves to version-03 (the OCR question left the
eval with `platform-infra`). What stays, as a checklist (run by you; GCP dev unless noted):

| # | Check | Status |
|---|---|---|
| C1 | GitHub **ingest** (https, tracked `main`): `sdlc-platform` ingested on GCP | ✅ R2 (2026-11-05) |
| C2 | GCS **ingest**: the three sample sources from the config store bucket | ✅ R2 (2026-11-05) |
| C3 | GitHub **user connection** on GCP: connect a fine-grained PAT on `/chat/connections` (first save on GCP also proves the IAM condition covers `secrets.create`), ask the chat to read a file of `agentic-sdlc-core` with `github_get_file`, disconnect, ask again → "not connected" | open |
| C4 | Bitbucket Cloud **user connection**: an Atlassian API token *with scopes* (`read:user:bitbucket`, `read:repository:bitbucket`) + your Atlassian email on `/chat/connections`; read a file of `agentic-sdlc-demo/agentic-sdlc-core` with `bitbucket_get_file` | open |
| C5 | AG-UI gate 5 (GitHub part): a second user whose GitHub account has no access to a private repo connects their own PAT and asks for a file there → the provider's 404/403 comes back as "no access", never another user's token | open (needs a private repo) |
| C6 | AG-UI gate 3: an answer from `search_knowledge` shows citations with links (GitHub blob URL for `sdlc-platform`, bucket object for the samples); Isha (no knowledge tool) and Ana (viewer, no team) never see `payments-code` / `sdlc-platform` citations | open |
| C7 | Retrieval eval: after the merge to `main` (R3) and a `sdlc-platform` re-ingest, `SDLC_EVAL=1 uv run --env-file .env pytest tests/evals -s` (local, live Vertex); record vector vs hybrid hit rates here | **Done 2026-11-05** (local, `7a5e4df`, 33 questions, passed). recall@5 / recall@3 / MRR: vector 0.939 / 0.864 / 0.698; vector+dedup 0.970 / 0.879 / 0.708; hybrid h1 = h2 0.955 / 0.879 / 0.707. Single-hop and sample-source questions 1.000 recall@5 in every variant; multi-hop recall@5 0.778 (vector) to 0.889 (dedup). Misses (0.50 everywhere): token forwarding agent -> MCP, how the MCP server picks searchable sources; hybrid drops one source for the rate-limit refusal question |

### R9 — N7 A2UI spike (§10)
Spike only, no product code until it passes: A2UI over AG-UI and A2A from one code path, citation cards from the
standard catalog, a version both GE and `@copilotkit/a2ui-renderer` accept, ADK's A2A server behind `sdlc_web`.
Output: a short findings note in §10 and a go/no-go for §10 Work items 2–4.

**Done 2026-11-05:** GO, build in version-03 (§10 "Spike findings").

### Moved to version-03 (2026-11-04)
- **N5 GCP operations (§5, remaining):** scale out `sdlc-app`; shared rate-limit store; CI deploy stages; custom
  hostnames + managed certificates; Cloud SQL private IP; staging (D4); E1/E4/E5/E6.
- **N6 backlog (§6):** Cloud + DC connections side by side, URL elicitation, Antigravity OAuth sign-in + Stage 8 gate,
  `explain` by UPN, ADK evals in CI, retrieval ranking, SharePoint / Office sources, write tools (D5).
- **N2:** Data Center checks, Antigravity in AG-UI gate 2, Confluence/Jira Cloud live checks (D2: no site), the H10
  PDF OCR live check (needs a source with scanned PDFs), source secrets in Secret Manager (first private source).
- **N7 build** (§10 Work items 2–4), unless the R9 spike makes a case for version-02.
- **Pending tasks** ([pending-task.md](pending-task.md)): agent runtimes (task 1); artifacts (task 3; decided
  2026-11-05).

### Version-02 exit
R1–R3 done; R5, R6, R7 and R8 (Cloud) done or explicitly moved with a reason; R9 spike written up with a go/no-go.
Then version-03 starts from "Moved to version-03" above.

## 20. Close-out (2026-11-05)

**Built in version-02:** N0 checks; N3 secrets review, reconcile job, `--check-secrets`, block list via bundles; N4
Cloud Trace + audit views; N1 ingest schedule; N7 A2UI spike (GO); N8 chat UX; N9 per-source groups; N10 direct
members; N11 rename; N12 `sdlc-platform` team + GitHub source; N13 config bundles from the bucket; N14 sample sources
in the bucket; N15 chat history (+ delete); `whoami(explain)` readable-sources fix; eval questions follow version-02
paths (CI-checked); `users.yaml` one line per user. Decisions: D1–D5 decided, D6 not pursued, D7 (agent runtimes)
open for version-03.

**Moved to version-03** (with reasons, §19 "Moved to version-03"): N5 operations and staging (D4), N6 backlog and write
tools (D5), N2 Atlassian / Data Center / PDF OCR live checks (D2, no source), the N7 build, the `infra-readers` group,
pending tasks 1 (agent runtimes) and 3 (artifacts). Drafted as [version-03.md](version-03.md).

### Handover checklist (run by the user)

| # | Step | Closes |
|---|---|---|
| H1 | Push the last commit (`git push origin version-02`) and merge the version-02 PR into GitHub `main` (mirror to Bitbucket if wanted). **Done 2026-11-05** (PR #2, `7a5e4df`) | R3 |
| H2 | `-Step config` (Przemek in the dev bundle); Przemek checks "who am I? explain" → team `sdlc-platform`, role `developer` | N10 (dev user) |
| H3 | `-Step images`, set `ingest_schedule` / `reconcile_schedule` in `dev.tfvars` if wanted, `-Step plan` (expect: reconcile job + SA, 2 custom roles, Cloud Trace role + env, scheduler only if scheduled; **no destroys**), `-Step apply` | N1, N3, N4 deploy |
| H4 | Reconcile dry run on GCP; block/unblock a test user via `blocked.yaml` + `-Step config` (§19 R5 steps 2–3) | N3 |
| H5 | One chat turn = one trace in Cloud Trace, no prompt text or argument values; its audit records by `trace_id` (§19 R6) | N4 |
| H6 | Next scheduled ingest run visible, if `ingest_schedule` was set (§19 R7) | N1 |
| H7 | R8 checklist C3–C7: GitHub + Bitbucket Cloud connections on GCP, AG-UI gates 3 and 5, retrieval eval after H1 + a `sdlc-platform` re-ingest (record the hit rates in R8). Eval **done 2026-11-05** (C7). Re-ingest **done 2026-11-05** at `7a5e4df`, local and GCP (80 changed, 25 deleted, 683 chunks, 408 LLM calls each) | N2 |

A failing step stays in version-02 until fixed (or is moved to version-03 with a reason written here); then mark the
milestone ✅ in Progress, switch CLAUDE.md's "Current plan" to version-03, and start version-03 at its P0.
