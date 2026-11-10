# Agentic SDLC — Implementation Plan version-03 (draft)

**Status: current (2026-11-05).** Version-02 closed 2026-11-06 (§20 H6, the first scheduled runs, passed).
First milestone: **P5 artifacts** (§P5): **done 2026-11-06** (F1, F2, F4, F5, F6; F3 sharing deferred).
Other milestones remain a proposal, confirmed one by one.

Follows [version-02.md](version-02.md). Architecture: [../ARCHITECTURE.md](../ARCHITECTURE.md); feature status
(reconciliation baseline, 2026-11-08): [../FEATURE_INVENTORY.md](../FEATURE_INVENTORY.md); GCP runbook:
[../GCP_DEPLOYMENT.md](../guides/GCP_DEPLOYMENT.md); secrets: [../SECRETS_REVIEW.md](../SECRETS_REVIEW.md); designs carried in:
[pending-task.md](pending-task.md) (tasks 1 and 3).

## Goals

1. **Production-shaped GCP:** enterprise identity (app roles, federated credentials, Entra apps in Terraform),
   custom hostnames, CI deploys, applied to GCP dev (the staging environment, P1, was dropped 2026-11-07).
2. **Richer agent output:** A2UI citation cards and an A2A endpoint (the GO from the version-02 N7 spike), and
   stored artifacts users can download.
3. **Autonomous agents:** CI and ops agents with their own workload identity, read + report back.
4. **More sources and connectors,** live-checked: Atlassian Cloud, Data Center editions, private repos.

## Milestones (proposal)

| # | Milestone | From | Waits for |
|---|---|---|---|
| P0 | Carry-in: anything from version-02 §20 that failed and was moved here | version-02 §20 | version-02 close-out |
| P1 | ~~Staging environment~~ dropped by the user 2026-11-07: no second GCP environment in version-03; P2 and P3 apply to GCP dev | N5, D4 | — |
| P2 | Enterprise identity: app roles defined in the tenant (E1, §P2: ✅ done 2026-11-07, live on localhost and GCP dev), federated credentials instead of client secrets (E4), Entra apps in Terraform (E5), no Azure CLI pre-auth outside dev (E6), per-environment Entra client: E4–E6 **parked** 2026-11-07; Graph overage fallback off (2026-11-07) | N5, version-00 E1/E4–E6, SECRETS_REVIEW §6 | E4–E6: parked (un-park when needed) |
| P3 | Operations: custom hostnames + managed certificates (drop the `*.run.app` exception), CI deploy stages (build → plan → apply with approval), Cloud SQL private IP, scale out `sdlc-app`, shared rate-limit store (if `sdlc-mcp` > 1 instance), log-based metrics + alerts on audit events, Secret Manager data-access logs | N5, N4, SECRETS_REVIEW §6 | — (GCP dev; P1 dropped) |
| P4 | A2UI citation cards in `/chat/` + A2A endpoint (§P4, ✅ done 2026-11-06: C1–C5, live on GCP dev) | N7 spike (version-02 §10 "Spike findings") | U1–U6 confirmed |
| P5 | Artifacts: store, list and download agent-generated files under RBAC | pending task 3 | Q4 (use cases, storage) |
| P6 | Agent runtimes: `ci_agent`, `ops_agent` with workload identity, read + report back; event intake through one gateway + Pub/Sub (§P6, intake designed 2026-11-06) | pending task 1, D7 | Q5 (ops report channel; runtime layout), Q3 (Bitbucket DC instance) |
| P7 | Write tools on behalf of the user (create issue, comment, PR) with UI confirmation | N6, D5 | P6 decisions (approval gates) |
| P8 | Connectors and sources: Atlassian Cloud live checks (incl. AG-UI gate 5 Jira part), Data Center editions (Bitbucket DC "who am I"), Cloud + DC side by side, URL elicitation, PDF OCR live check (a source with scanned PDFs), source secrets in Secret Manager (first private source), SharePoint / Office documents, GitHub App tokens, `inherit_from_source` | N2, N6 | Q3 (Atlassian site, DC instance, private sources) |
| P9 | Quality and tooling: ADK evals in CI, retrieval ranking (re-ranker, query entities), `explain` by UPN, Antigravity OAuth sign-in + Stage 8 gate, OBO where providers support it, OPA/Cedar if rules outgrow YAML, admin UI over config | N6, version-00 Stage 8/9 | — |
| P10 | EGM document flow: full-context agent drafts, isolated Goldfish reviewers critique, user approves (§P10, ✅ done 2026-11-07 locally: G1–G3; G4–G9 done 2026-11-07 (live checks passed); deployed to GCP dev with `-Step config` (user, 2026-11-07)) | user request 2026-11-05 | P5 F2 live check |
| P11 | Keyword (full-text) search next to vector + graph retrieval: Postgres `tsvector` + GIN on `chunks`, fused with the vector ranking; kept only if the retrieval eval improves (§P11, ✅ K1–K2 done 2026-11-07; live on GCP dev, eval gate passed there) | user request 2026-11-06 | — |
| — | Per-source Entra group `infra-readers` (or a real one) in the tenant | N9 | a source that needs its own group |
| — | Gemini Enterprise registration (A2A agent + OAuth authorization): ✅ works (user, 2026-11-07) against GCP dev `/a2a`. GE authorization = Entra authorization-code flow (authorize/token v2 endpoints of the tenant, scope `api://<sdlc-mcp>/access_as_user offline_access`, PKCE on, client secret in the body: basic HTTP auth off); the Entra client app has GE's redirect URI as a **Web** platform URI (take the exact value from the `AADSTS50011` error). No code change: the C5 path (bearer token through the app's oauth2-proxy) serves GE as is | version-02 §7 | — |

**Order (decided 2026-11-05):** P5 first (Q4 answered). Then proposed: P4 (no outside dependencies) → P2
(enterprise identity on GCP dev; P1 staging dropped 2026-11-07) → P3 → P6 / P7 as their decisions land; P8 and P9
by priority.

## P2 — Enterprise identity (E1 started 2026-11-07; P1 staging dropped, so P2 targets GCP dev)

**E1 app roles (scope confirmed 2026-11-07: app roles only, E4 parked).** The code already read the `roles`
claim and config already accepted `app_role:`; E1 adds the roles in the tenant, grants them in config and
proves they grant exactly what the groups grant. Groups and app roles combine (union); overage drops only
`groups`, never `roles`.

| # | Step | Exit gate | Status |
|---|---|---|---|
| E1a | App roles on `sdlc-mcp`: `SDLC.User`, `SDLC.Admin`, `SDLC.Payments.Developer`, `SDLC.Payments.Lead`, `SDLC.Platform.Developer`, `SDLC.Platform.Lead` (`entra_setup.ps1` `$AppRoles`, add/update only; `-AppRoleUser` / `-AppRoleUserRoles` assigns them to one user) | script parses; `-DryRun` lists the roles to add | ✅ code 2026-11-07 |
| E1b | Config grants: `roles.yaml` bindings (`SDLC.User` → viewer, `SDLC.Admin` → admin), `teams/payments.yaml` and `teams/sdlc-platform.yaml` membership (developer / lead). sdlc-platform now has app-role members next to users.yaml | `validate` OK; `sdlc-config diff`: no existing persona changes | ✅ 2026-11-07 |
| E1c | Tests: app-role personas (`approle-*`, `mixed-dev`, `unknown-app-role`) in `personas.yaml`, matrix + data rows, `tests/policy/test_app_roles.py` (each app-role persona resolves exactly like its group twin; config role values = `$AppRoles`), `test_app_roles_survive_group_overage` (MCP, overage token + roles) | tests pass | ✅ 2026-11-07 |
| E1d | Tenant (user, admin account confirmed): run the script with `-AppRoleUser <a user without sdlc groups>`; live check `whoami(explain=true)`, a payments `review_code`, then unassign → access gone at the next token | live check on localhost + GCP dev (`-Step config` publishes the config) | ✅ 2026-11-07: roles created and assigned in the Entra admin center (user), live check passed; GCP dev: `-Step config` published, works (user, 2026-11-07) |

**Graph overage fallback off (2026-11-07):** `platform.yaml` `identity.groups.overage_fallback: none`. App roles
are the overage path; a user whose token hits overage gets no groups (fail closed), only app roles. The Graph
client secret was never set (not in `.env`, so not on GCP), so nothing to remove; the `GroupMember.Read.All`
permission on `sdlc-mcp`, if ever granted, can be revoked (admin). `graph_transitive_member_of` turns it back on.

**E5 Entra apps in Terraform, E6 no Azure CLI pre-auth outside dev: parked (2026-11-07).** `entra_setup.ps1`
stays the provisioning path; GCP dev keeps sharing the dev Entra apps (Azure CLI pre-authorized).

**E4 federated credentials: parked (2026-11-07).** Design kept for later: Entra trusts the Cloud Run service
account's Google ID token (federated credential: issuer `https://accounts.google.com`, subject = SA unique id,
audience `api://AzureADTokenExchange`) sent as `client_assertion`. Graph fallback: `GraphGroupResolver` takes
an assertion source (metadata server). oauth2-proxy: needs a spike (`entra-id` provider with federated token
file + a sidecar that refreshes the token). Gemini Enterprise gets its own client so it can keep a secret.

## P4 — A2UI cards in the chat + A2A endpoint (from the version-02 N7 spike)

Started 2026-11-06. Builds on version-02 §10 ("Spike findings": GO). Gemini Enterprise registration stays out of
scope (needs a GE app, workforce pool and licences; milestone row "—" above).

**Decisions (confirmed by the user 2026-11-06; P4 before P10):**

| # | Decision |
|---|---|
| U1 | A2UI **v0.9, standard catalog only**, built **deterministically from MCP tool results** with `a2ui-agent-sdk`'s builder (`a2ui.builder.v0_9`). The model never writes UI; `ag_ui_adk`'s `generate_a2ui` (a model writes it) is not used |
| U2 | Cards for: `search_knowledge` / `graph_query` citations, `whoami`, connected-tool results (`*_get_*`). Artifact cards stay hand-written: their links are same-origin `/artifacts/<id>`, which an A2A client such as GE cannot open |
| U3 | Links only `http(s)` (checked before building), opened with the catalog's `openUrl`. A2UI user actions are input to the agent, **never authorization** |
| U4 | The model does **not** see the A2UI JSON: it travels next to the tool result for the transports, so tokens are not spent on it and it cannot be echoed or altered (C1 checks how `ag_ui_adk` forwards it) |
| U5 | A2A endpoint on the agent service (`/a2a`), behind the same Entra checks as `/agui`: user id = token `oid` (never ADK's `A2A_USER_<context_id>` fallback), the token request-scoped (never in session state), client state sanitised, one A2A context = one session in the existing store, another user's context refused |
| U6 | How A2A clients reach it: callers send `Authorization: Bearer <Entra token>` (GE's model). Locally through oauth2-proxy as an API route that accepts bearer tokens, or the agent port for tests only; GCP exposure decided in C5 |

**Milestones:**

| # | Scope | Exit gate | Status |
|---|---|---|---|
| C1 | `libs/sdlc_agent/a2ui_cards.py`: tool result → v0.9 operations (`createSurface` + `updateComponents`); `after_tool_callback` attaches them for the transports, not the model | Unit tests: valid v0.9 for each covered tool (validated against the SDK's catalog models); non-`http(s)` links dropped; malformed or empty results give no surface; the model-visible tool result is unchanged | ✅ Built 2026-11-06: `a2ui_cards.py` (citations, whoami, 4 connected tools; strict validation with `STRICT_VALIDATION`, which also rejects unknown components/functions, missing fields, dangling refs and extra props; the default processor checks only the catalog id), `after_tool_callback` (drops forged `a2ui_operations` from any tool) + `before_model_callback` (copies, session keeps the cards), wired into `user_agent`; `tests/agent/test_a2ui_cards.py` 16 passed. Finding for C5: the chat renders A2UI `Text` as plain text; check how GE renders it (Markdown?) before exposing provider text there |
| C2 | ~~Chat renders A2UI~~ → **chat keeps its compact renderers; A2UI cards made compact for A2A clients** (changed 2026-11-06) | The chat shows the collapsed identity line and the document chips with links as before; the A2UI surfaces are compact and strictly valid | ✅ 2026-11-06. Tried live: CopilotKit 1.79 knows the basic catalog only as `…/v0_9/basic_catalog.json` while `a2ui-agent-sdk` sends `…/v0_9/catalogs/basic/catalog.json` ("Catalog not found"; fixable by registering the id client-side), and the full cards were too big next to the chat's compact design, which the basic catalog cannot express (no collapsible, no chip). Decision (yours): the chat keeps its own renderers (no `a2ui` runtime option, no client catalog, no new dependency); the agent still attaches cards to tool results (ignored by the chat) for A2A clients (C3). Cards are now compact: search/graph = one caption "Sources · N docs" + a row of chips (title or file name, ×hits; a borderless `openUrl` button when linked, plain text otherwise; max 10, then "+k"); whoami = one line "Signed in as … · teams · roles · groups" + a `Modal` "Details"; connected tools keep a small card with a borderless Open |
| C3 | A2A server: `google-adk[a2a]`, `to_a2a(...)` mounted at `/a2a` in `sdlc_web` behind the Entra middleware, a call-context builder from the verified `oid`, A2UI as `DataPart` (`application/json+a2ui`), agent card at `/.well-known/agent-card.json` | Tests (FakeEntra): no token → 401; a valid user gets an answer with the A2UI DataPart; another user's context id → refused; no token in persisted session events; client state stripped | ✅ 2026-11-06: `sdlc_web/a2a.py`, on when `SDLC_A2A_AGENT` names the agent (`SDLC_A2A_URL` = advertised URL; default the request's). **A2A 0.3** (`a2a-sdk` 0.3.x, JSON-RPC) for Gemini Enterprise; re-check in C5. Built on a2a-sdk's `A2AStarletteApplication` + ADK's `A2aAgentExecutor` (not `to_a2a`: its in-memory runner and sub-app lifespan don't fit), sharing the session store with /agui (A2A chats appear in the chat's history). Identity: call context = verified `oid`, no headers in it (the default builder would copy the token into state). Isolation: `OwnerTaskStore` (another user's task = not found, for get/cancel/resubscribe/continue), another user's or a malformed context id = "unknown context" (ids `[A-Za-z0-9_-]{1,128}`, Agent Engine's alphabet). Input: text parts only (forged function results, files, client metadata and state dropped); no push notifications. Output: A2UI cards as separate DataParts `mimeType: application/json+a2ui`, function result without them; failures answer a generic message (details logged). Card public at `/.well-known/agent-card.json` (bearer `entra` scheme, A2UI extension `https://a2ui.org/a2a-extension/a2ui/v0.9`, to re-check in C5). Tasks in memory (per instance, 5000 max). Tests `tests/web/test_a2a.py` (6, scripted agent `a2a_probe` with the real card callbacks) |
| C4 | Local A2A access: oauth2-proxy route for `/a2a` with bearer tokens (both proxies), a small `scripts/a2a_client.py` | A local A2A client with your Entra token gets the same answer and cards as the chat; without a token 401 | ✅ 2026-11-06: both oauth2-proxies accept `Authorization: Bearer` (`SKIP_JWT_BEARER_TOKENS`, `EXTRA_JWT_ISSUERS` = the tenant v2 issuer with the sdlc-mcp client id as audience; the agent re-validates scope and tenant), `/a2a` is an API route (401, no login redirect), the card route skips auth; compose sets `SDLC_A2A_AGENT=user_agent` (card URL from the request: localhost and the tunnel each advertise their own). Checked: card 200 on both; no token / a bad token = 401 on both. `scripts/a2a_client.py` (answer, tools, A2UI card texts and links, contextId). Note: bearer tokens now pass the proxy for every upstream (all re-validate, as `/mcp` already accepts them directly). Live check (user, 2026-11-06): a test user's token gets the answer and cards on localhost and the tunnel; chat sign-in unchanged |
| C5 | GCP: deploy, decide exposure (U6), audit + trace checks | The same A2A call works against GCP dev; audit records carry the A2A context as `agent_session_id`; no prompt content in Cloud Trace | ✅ 2026-11-06 (live on GCP dev). U6 decided: same path as local, bearer tokens through the app service's oauth2-proxy sidecar (`/a2a` API route, public card), no new service or ingress. `infra/gcp/run.tf`: the C4 proxy settings, `SDLC_A2A_AGENT=user_agent`, `SDLC_A2A_URL=https://<app host>/a2a` (the agent sees 127.0.0.1 behind the sidecar, so the card URL is configured). Agent Engine: ADK passes the A2A context id as the session id (alphabet `[A-Za-z0-9_-]`, which `_CONTEXT_ID` enforces) and refuses a session of another user. Limit: task/context owner maps are per instance (up to `app_max_instances`): `tasks/get` of a task from another instance answers not found, another user's context on another instance fails generically (the session store still refuses it); `message/send` returns the whole task, so clients don't need `tasks/get`. Checked: card, answer + cards, continuation and 401 without a token (user); audit `tool_call` records of both turns carry the A2A contextId as `agent_session_id`, one `trace_id` per turn; Cloud Trace spans hold no prompt, answer, token or argument values (`tool_call_args` = `{}`; the a2a-sdk adds ~70 internal spans per turn, names only) |

## P5 — Artifacts (from pending task 3)

**Decisions (2026-11-05, Q4):**

| # | Decision |
|---|---|
| A1 | First use cases: **design / review documents** and **user stories / reports**, as text files (Markdown first) |
| A2 | Metadata in **Postgres** (`sdlc.artifacts`); `sdlc_app` gets a **narrow write grant on that table only** (SELECT, INSERT, DELETE), row-level security by owner oid. Knowledge tables stay read-only for `sdlc_app` |
| A3 | **Owner only.** Anyone else (admins included) gets "not found". Team sharing + classification inheritance = a later milestone (F3) |
| A4 | Retention **7 days** from creation, as the GCP artifact bucket's lifecycle today (`artifact_retention_days`) |
| A5 | Written and read **through the MCP server** (tools + an HTTP download API), never through ADK's artifact service (stays `memory://`), so there is one audited path |

**Design:**
- **Content store** (`libs/sdlc_artifacts`): put / get / delete by object key `artifacts/<owner oid>/<artifact id>`;
  backends `file://<folder>` (compose volume on `core-mcp`, like the user secret store) and `gs://<bucket>/<prefix>`
  (GCP). Selected by `SDLC_ARTIFACT_STORE`; empty = artifacts off (tools answer "not configured").
- **Metadata** (migration `005_artifacts.sql`): `id` uuid, `owner_oid`, `name`, `media_type`, `size_bytes`, `sha256`,
  `agent_session_id` (correlation only), `created_at`, `expires_at`. RLS ENABLE + FORCE; policy for `sdlc_app`:
  `owner_oid = current_setting('app.user_oid')`, set per transaction by `sdlc_db.owner_scoped(conn, oid)` from the
  verified token. No grant to `sdlc_ingest`. Not knowledge data, so no `source_id` / `classification_rank` yet (F3
  adds classification for sharing).
- **MCP tools** (`tools.yaml`, granted to `viewer` and up, persona-matrix rows): `save_artifact(name, content,
  media_type="text/markdown")` → id, size, expiry, download path; `list_artifacts()`; `read_artifact(id)` (the agent
  revises a document); `delete_artifact(id)`.
- **Limits:** text media types only (`text/markdown`, `text/plain`, `text/csv`, `application/json`), 1 MiB per
  artifact, 50 live artifacts per user, file names `[A-Za-z0-9._ -]`, max 100 characters, with a matching
  extension. Expired rows are not listed and are deleted on the owner's next save/list.
- **Download API** on the MCP server, through oauth2-proxy like `/connections/`: `GET /artifacts/` (list),
  `GET /artifacts/{id}` (download: `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`, never
  rendered as HTML on our origin), `DELETE /artifacts/{id}` (needs `X-SDLC-Request: 1`). Same token checks as MCP
  (block list included); the caller's policy must allow `list_artifacts` / `read_artifact`.
- **Audit:** `artifact_change` (create / delete: oid, artifact id, media type, size, outcome) and `artifact_access`
  (download / read: oid, artifact id, outcome); never the content or the file name. Tool calls are also in `tool_call`.
- **Chat:** the agent links the download path (`/artifacts/<id>`) in its answer; the chat app needs no new data path.

**Milestones:**

| # | Scope | Exit gate | Status |
|---|---|---|---|
| F1 | `libs/sdlc_artifacts` (file + GCS), migration 005 + `owner_scoped`, MCP tools, config + persona rows, compose volume | Tests: a user saves, lists, reads and deletes their own artifact; another user gets "not found"; limits enforced; RLS test in `tests/db`; audit records | ✅ Built 2026-11-05: `tests/db/test_artifacts.py` (RLS + tools end to end), `tests/artifacts/`; migration 005 applied to the local dev DB, core-mcp logs `artifacts on (file store, 7.0 days)`; full suite 779 passed. GCP: needs `-Step db` (migration) with F4 |
| F2 | Download API + oauth2-proxy routes (localhost **and** the tunnel) + agent instruction to link artifacts | A download works on localhost and the tunnel; no access without a session; another user's id answers 404 | 🔨 Built 2026-11-05: `artifacts_api.py` (GET list / GET download / DELETE with `X-SDLC-Request: 1`; 401 without token, 403 without the tool, 404 for others' ids; attachment + `nosniff` + CSP sandbox), proxy upstream (both local proxies answer 302 to sign-in), agent instruction, chat card for `save_artifact` / `list_artifacts` (links built from the UUID only). Tests: `tests/db/test_artifacts.py`, UI `results.test.ts`. Live check 2026-11-05: download works (localhost). The chat's **Artifacts panel** (version-02 placeholder) now lists the caller's documents from `GET /artifacts/` (download, delete with confirmation, refresh when the chat saves one) |
| F5 | Review in the chat (asked 2026-11-05): overlay modal to view a saved document (Lines with numbers + Markdown Preview, no raw HTML or images), inline line comments, "Attach to chat" = one user message with a reference + the comments (decision: comments live in the conversation, the agent reads the text with `read_artifact`) | Open from the panel or a chat card; attaching starts an agent run that revises the document and saves a new version | 🔨 Built 2026-11-05 (`ArtifactViewer`, `ArtifactReviewHost`, `lib/review.ts` + tests; `react-markdown` 10.1.0 pinned). Live check passed 2026-11-05 (attach → agent read the document and saved a revised version) |
| F6 | Versions (asked 2026-11-05: "can the agent update the same document?"; decision: versions, not overwrite): `save_artifact(replaces=<id>)` adds version N+1 of the same document; stable id and link (latest), `read_artifact(id, version)`, `GET /artifacts/{id}?version=N` and `/versions`, delete removes all versions; viewer version picker, drafts per version, attach message names the version | The agent revises a reviewed document as v2 of the same entry; v1 stays viewable | 🔨 Built 2026-11-05: migration 006 (applied to the local dev DB, 2 rows backfilled as v1), `test_versions_of_one_document`; full suite 781 passed. Live check passed 2026-11-05 (revision saved as v2 of the same entry, v1 viewable). Review fixes 2026-11-06: `save_artifact(replaces=…)` needs `base_version` and refuses when a newer version exists (audit outcome `stale`; the agent asks the user); older versions are read-only in the viewer (no line selection, comments or "Attach to chat"; a button opens the latest); `read_artifact(numbered=true)` numbers lines as the viewer does (saving them back is refused); `?version=` accepts ASCII digits only (`²` was a 500); the comment being written survives closing the viewer, and Escape in a text field no longer closes it. Open: live recheck. Undecided: versions count toward the 50 limit; a new version may change name / media type |
| F3 | Team sharing + classification inheritance | later (A3) | not planned |
| F4 | GCP: MCP service account gets `objectUser` on the artifact bucket (the agent's grant is removed), `SDLC_ARTIFACT_STORE` on `sdlc-mcp`, proxy routes; Terraform run by the user | F1/F2 gates on GCP dev | 🔨 Built 2026-11-05 (not applied): bucket grant moved from `sdlc-app` to `sdlc-mcp` (`artifact_store_mcp`; the plan shows the old `artifact_store_agent` member destroyed), `SDLC_ARTIFACT_STORE` + `SDLC_ARTIFACT_RETENTION_DAYS` on `sdlc-mcp`, proxy upstream `/artifacts/`. Your steps: `-Step images`, `plan`, `apply`, then `-Step db` (migrations 005 + 006) right after, **and `-Step config`** (the artifact tools are new in `tools.yaml` / `roles.yaml`; without a new bundle the panel answers 403). 2026-11-06: images/plan/apply/db done and checked (005 + 006 applied, `artifacts on (gcs store, 7.0 days)`, bucket `objectUser` only for `sdlc-mcp`); first try failed with 403 because the bundle was still `44ba0b4` → `-Step config`. **Done 2026-11-06:** bundle `1a1df4a`, audit create v1 → download → read → update v2 → download (all `ok`), two objects under `artifacts/<oid>/` in the bucket, no MCP errors |

## P6 — Agent runtimes and event intake (from pending task 1; proposal, intake designed 2026-11-06)

Base design (runtimes, workload identity, read + report back, guardrails): [pending-task.md](pending-task.md) task 1,
still valid. This section adds **how events reach the runtimes**: CI events (Bitbucket first), ops events (GCP alerts)
and signals from other agents. Nothing is built.

**Decisions (2026-11-06):**

| # | Decision |
|---|---|
| R1 | First sources: **Bitbucket Cloud + Data Center** (webhooks) and **GCP Cloud Monitoring alerts**. GitHub and generic HMAC webhooks (Alertmanager, PagerDuty) come later as adapters on the same gateway |
| R2 | **One common event gateway** for every source: the only public intake; verifies the caller, matches a `Trigger`, normalises, publishes |
| R3 | **Event bus = Pub/Sub, envelope = CloudEvents 1.0.** One topic per env, one push subscription per runtime, routed by attribute filters |
| R4 | Agent-to-agent: **notifications on the bus** (`sdlc.agent.*` events, fan-out), **requests over A2A** (needs an answer; the A2A endpoint is live from P4) |
| R5 | Runtimes accept **only Pub/Sub push** from their own subscription, never raw webhooks; they have no DB credentials, so dedupe + run records go through the MCP server |

**Flow:**

```
Bitbucket Cloud webhook       ┐
Bitbucket DC webhook          ┤  POST /events/<adapter>
(later: GitHub, generic HMAC) ┘        │
                                       ▼
                        event-gateway (Cloud Run, public)            GCP Cloud Monitoring
                         1 verify caller (per adapter)                 └─ Pub/Sub notification channel
                         2 match a Trigger (config/triggers/)               → topic alerts-raw-<env>
                         3 normalise → CloudEvent (size-capped)              → push (OIDC) to gateway
                         4 rate-limit, set routing attributes
                         5 publish; 202 + event id
                                       │
                                       ▼
                   Pub/Sub topic  sdlc-events-<env>   (CloudEvents 1.0; attributes: type, source,
                   target_agent, team, dedupe_key, hop_count; ordering key = PR / incident)
                    │                     │                          ▲
        sub ci-agent (filter              sub ops-agent (filter       │ agents publish
        target_agent="ci_agent")          target_agent="ops_agent")   │ sdlc.agent.* notifications
                    │ push + OIDC          │ push + OIDC               │ (their own service account)
                    ▼                      ▼                           │
           ci runtime (Cloud Run)   ops runtime (Cloud Run) ───────────┘
            verify push token → claim_event (MCP, dedupe) → agent run (app-only Entra token → MCP)
            → report back → ack.  Failure: retry with backoff → dead-letter topic after N tries
```

**Design:**
- **Gateway** (new component `event_gateway/`, Cloud Run, public; shared code in `libs/sdlc_events`): holds the adapter
  secrets (references through `sdlc_secrets`), checks callers (table below), matches a `Trigger`, rate-limits per
  Trigger, publishes, answers `202` + event id. It holds only `pubsub.publisher` on the events topic. Unknown or
  disabled Triggers and bad signatures answer 401/404 and are audited (`event_intake`, no payload).
- **Envelope:** CloudEvents 1.0. `type` e.g. `sdlc.ci.pull_request.opened`, `sdlc.ci.build.failed`,
  `sdlc.ops.alert.opened` / `.closed`, `sdlc.agent.finding`; `source` (adapter + repo / service), `subject` (PR,
  commit, incident), `data` = a size-capped summary + links, never the full payload. Payload text is **untrusted
  data** (prompt injection): handed to the agent as data, never used verbatim as tool arguments.
- **Routing is config:** new config kind `Trigger` (`config/triggers/<id>.yaml`, as sketched in pending task 1 §5):
  adapter, accepted callers (workspace / project / repo; monitoring project), target agent, team, report channel,
  rate limit, dedupe window, `enabled`. The gateway sets `target_agent` / `team` from the matched Trigger; Terraform
  owns one subscription per runtime with a fixed filter. **New exception to "only MCP servers and ingest read config":**
  the gateway reads the `Trigger` kind only, through `ConfigStore.current()`.
- **Ordering and bursts:** ordering key per PR / incident (never two runs on the same PR at once); Pub/Sub retries with
  backoff, a dead-letter topic after N attempts, replay by seek.
- **Idempotency:** dedupe key = the adapter's delivery id (table) within the Trigger's window. The runtime calls a new
  MCP tool `claim_event(event_id, dedupe_key)` (service roles only) → `sdlc.agent_runs` (RLS by service principal oid,
  status / timings / outcome); a second delivery answers "already handled" and is acked without a run. Audited.
- **Run bounds:** push ack deadline is ≤ 600 s, so each run has a timeout below it, a tool-call cap and a token budget.
  Longer runs later: ack after the claim and hand off to a Cloud Run Job execution (not needed for read + report back).
- **Agent signals:** an agent publishes `sdlc.agent.*` with its own service account (topic IAM decides who may
  publish); `hop_count` is incremented and events above a limit are dropped; a runtime never consumes events whose
  `source` is itself. Requests that need an answer use A2A with the caller's own app-only token.
- **Identity** (unchanged from pending task 1 §4, milestone A1): app-only Entra tokens with an allowed app role, never
  a user token; the reporter uses a **reporting-only service credential**.
- **Local:** Pub/Sub emulator in docker compose (profile `autonomous`, not started by `up`), same client code; the
  gateway reachable through the Cloudflare tunnel for Bitbucket Cloud webhooks (hostname
  `events-sdlc-dev.shaheenks.co.in`, to be added in the Cloudflare dashboard).

**First adapters:**

| Adapter | Caller check | Dedupe key | First events | Report back |
|---|---|---|---|---|
| `bitbucket-cloud` | Webhook secret: `X-Hub-Signature` HMAC-SHA256 over the raw body (constant-time compare); workspace + repo matched against the Trigger. Later, optionally: Pipelines OIDC for pipeline-initiated calls | `X-Request-UUID` | `X-Event-Key` `pullrequest:created` / `pullrequest:updated`, `repo:commit_status_updated` (failed build) | Code Insights report on the commit (+ PR comment), via a repository access token (`pullrequest:write`) through `sdlc_secrets`; `api.bitbucket.org` in `allowed_hosts` |
| `bitbucket-dc` | Webhook secret: `X-Hub-Signature` HMAC-SHA256; project + repo matched. The DC instance must reach the gateway's public URL | `X-Request-Id` | `pr:opened`, `pr:from_ref_updated`, build status | Code Insights report / PR comment via a project or repo HTTP access token (`sdlc_secrets`); DC host in `allowed_hosts` |
| `gcp-monitoring` | No public webhook: alert policy → Pub/Sub notification channel → `alerts-raw-<env>` (publisher = Monitoring's notification service agent) → authenticated push to the gateway (Google-signed OIDC token of the push service account, audience checked) | `incident.incident_id` + `incident.state` | `open` / `closed` incidents (policy, resource, summary) | Open (Q5): the API has no incident annotation, so a channel message (Google Chat / Teams / email) |

Both Bitbucket editions share one normaliser. `sdlc_connectors/providers.py` already knows the Cloud vs Data Center
base URLs and auth styles (user connections); the reporter reuses that for its service credential, not the per-user
PAT path. Remote calls go through `sdlc_connectors.http.HttpClient` (host allowlist). Live DC checks need the instance
from Q3.

**Alternatives not chosen:** direct webhook → runtime (no buffering or retries, every runtime public, secrets
everywhere); Cloud Tasks (point-to-point: no fan-out or filters for agent notifications); Eventarc (no Bitbucket or
GitHub sources; one more layer over Pub/Sub without benefit here).

**Milestones:**

| # | Scope | Exit gate | Status |
|---|---|---|---|
| A1 | Identity (pending task 1 §10 A1): MCP verifier accepts allowed app-only tokens, `Principal.kind`, app-role bindings, `service_header_provider`, personas `ci-agent` / `ops-agent` | An app-only test token gets exactly the ci-agent role's tools and sources; an app token without an allowed role gets 401 | proposed |
| E1 | `libs/sdlc_events` (CloudEvent model, adapter verifiers, normaliser, publisher with emulator + Pub/Sub backends) + `Trigger` config kind (schema, `_KINDS`, CODEOWNERS rule, tests) | Unit tests: valid and forged Bitbucket Cloud / DC signatures, Trigger matching (wrong repo = rejected), size caps, `sdlc-config validate` on example Triggers; CI passes without `.env` | proposed |
| E2 | `event_gateway` component + `bitbucket-cloud` / `bitbucket-dc` adapters; compose profile `autonomous` with the Pub/Sub emulator; tunnel hostname | A real Bitbucket Cloud webhook through the tunnel lands on the emulator topic as one CloudEvent; a forged signature gets 401 and is audited; a disabled Trigger publishes nothing | proposed |
| E3 | Runtime consumer in `libs/sdlc_runner` (push verification, run bounds, dead-letter handling), MCP tool `claim_event` + migration `agent_runs` (RLS, `tests/db`, tools.yaml + persona rows), `ci_agent` with Code Insights / PR-comment report back | A PR on a test repo gets one report; a redelivered event produces no second report; an injected PR description does not change tool use; audit shows gateway → run → tool calls → report with one run id | proposed |
| E4 | `gcp-monitoring` adapter (notification channel → `alerts-raw` → gateway) + `ops_agent`; report channel per Q5 | A test alert (open, then closed) produces one message per state; duplicates are dropped | proposed |
| E5 | Agent notifications on the bus (`sdlc.agent.*`, hop limit, no self-consumption); agent requests over A2A with app-only tokens | An `ops_agent` finding reaches a subscribed agent once; a loop stops at the hop limit; an A2A request from `ci_agent` is authorized as `ci-agent`, not as a user | proposed |
| E6 | GCP: topics, subscriptions (filters, ordering, dead letter), push service accounts, gateway + runtime services, notification channel; Terraform run by the user | E2–E5 gates on GCP dev | proposed |

**Rules (proposed for CLAUDE.md when E1 starts):** the gateway is the only public intake for events; runtimes accept
only Pub/Sub push from their own subscription; event payloads are untrusted data; the gateway reads only the
`Trigger` config kind; runtimes never get DB credentials or user tokens.

## P10 — EGM document flow (Elephant-Goldfish Model, https://egm.dev/)

**Decisions (2026-11-05):**

| # | Decision |
|---|---|
| E1 | Only for **document work** (designs, user stories, reviews, reports). Quick Q&A stays a single turn. No reviewer runs until the user says go |
| E2 | Reviewer lenses are **skills served by MCP** (tag `goldfish-lens`), granted in `config/`; teams can add their own |
| E3 | Starts after P5 (F2 live check). Drafts and review reports are saved as P5 artifacts |

**Design:**
- **Elephant** = `user_agent` (conversation, team context, knowledge tools, artifacts), guided by the flow skill
  `egm-document-flow`: brainstorm → draft → ask "review with Goldfish?" → review → resolve (PROPOSE FIX / CONTEST,
  only user-approved edits, at most one re-review) → approve → save `<name>.md` + `<name>-review.md`.
- **Goldfish** = agent-side tool `goldfish_review(draft, lenses)` (`libs/sdlc_agent/goldfish.py`). One nested ADK run
  per lens, run concurrently. Each run, like `AgentTool`, has a fresh in-memory session and sees only the draft and
  the lens name. Unlike `AgentTool`, its state starts **empty**. Reviewers load their lens with `load_skill` and may
  check claims with `search_knowledge` / `graph_query`, all through MCP **as the user**. A lens the user can't see is
  reported `unavailable`. A tool-less synthesizer dedupes the findings into Blocker / Major / Nit, each traced to
  its lens.
- **Lenses:** `lens-zoom-out`, `lens-comprehension`, `lens-design-critic`, `lens-implementation-readiness`
  (`skills/core/`); viewer gets `tag:goldfish-lens`. `design-review` stays for now.
- **Audit correlation:** a `_conversation_id` ContextVar in `sdlc_auth.adk`, set by the tool, keeps the parent
  conversation id in `X-SDLC-Agent-Session` for the nested MCP sessions (each reviewer opens and closes its own).
- **Limits:** `max_lenses` 6, `max_llm_calls_per_reviewer` 8, draft size capped. About 10–20 model calls per review.
- No new MCP tools, so no `tools.yaml` changes; authorization is unchanged.
- **Team customization (proposed 2026-11-07, G6–G8):** teams change *behaviour* (content, defaults, prompts), never
  *permissions* (roles, `Source.access`, MCP enforcement); team text is guidance, never authorization. Layers, lightest
  first: (1) `AGENT_ADDENDUM.md` guidance and (2) team add-on skills, both existing; (3) **typed team skills**: `tags`
  on team add-on skills, limited to a platform list (`goldfish-lens`, `brief-questions`, `doc-template`) and applying
  only inside that team; (4) **structured flow defaults** `addons.flows.document` (per document type: lenses,
  `required_lenses`, template, brief question pack, `max_rereviews`), validated (only skills the team can see,
  unknown keys fail) and served as data by `get_agent_context`; (5) **limits** (`max_lenses`, calls per reviewer)
  moved from code into `platform.yaml`, which teams may only lower. Precedence: platform defaults → team defaults →
  the user's request in the chat (add / drop optional lenses the user can see; `required_lenses` cannot be dropped,
  the flow says so); platform caps always apply. Several teams: optional lenses unioned up to the cap, required ones
  all apply (if they do not fit, the flow tells the user rather than dropping one), template / brief conflicts → ask
  which team the document is for (else `context.default_project`). **When the team is decided (G9):** brainstorming
  runs in broad context (all the user's teams as short summaries, knowledge across every readable source) and only
  collects hints; the team is settled in the brief (named in the chat → `resolve_team` → `default_team` → ask) and
  confirmed with it, then the team's full context and defaults apply to the draft and review. Example:

  ```yaml
  addons:
    flows:
      document:
        types:
          design:     { template: payments-design-template, lenses: [lens-design-critic, lens-implementation-readiness],
                        required_lenses: [payments-pci-lens] }
          user-story: { brief: payments-story-questions, lenses: [lens-comprehension, lens-implementation-readiness] }
        max_rereviews: 1            # may only lower the platform value
  ```

**Milestones:**

| # | Scope | Exit gate | Status |
|---|---|---|---|
| G1 | `goldfish.py` + conversation-id ContextVar | `tests/agent/test_goldfish.py` (stub LLM). A reviewer sees no parent history and empty state; MCP calls carry the user token and the parent conversation id; a hidden lens is reported `unavailable`; the lens cap holds; synthesizer output is validated | ✅ 2026-11-06: `libs/sdlc_agent/src/sdlc_agent/goldfish.py` (`make_goldfish_review(mcp_url, model)` → FunctionTool), `sdlc_auth.adk.set_conversation_id`; `tests/agent/test_goldfish.py` (7, scripted model + real test MCP server). As built: the **tool** loads each lens with `load_skill` as the user (one MCP session, audited `skill_access`) and puts its text in the reviewer's instruction (one model call less per reviewer, the lens is always applied; a denied lens never starts a reviewer); reviewers get only `search_knowledge` / `graph_query` (filtered), their own MCP session each, `max_llm_calls` 8, 240 s timeout; unusable output = lens `failed`, never the whole review. Synthesizer: merged severity = the highest it cites, unknown or reused ids dropped, uncited findings kept; unusable output = grouped without merging. Result: `lenses` (ok / unavailable / failed), `counts`, `findings` by severity (each with `lenses` + `sources`), `summary`, `report_markdown`. `list_skills` has no tags, so the lens list is explicit (default the four `lens-*`); any skill the user can load works as a lens |
| G2 | Flow + lens skills, `skills.yaml`, viewer grant, `skill_rows` | `sdlc-config validate` + `diff` reviewed; policy/config tests pass | ✅ 2026-11-06: `skills/core/egm-document-flow` (tag `general`: brainstorm → draft → gate → `goldfish_review` → PROPOSE FIX / CONTEST, only approved edits, one re-review at most → save `<name>.md` + `<name>-review.md`) and the four `lens-*` (tag `goldfish-lens`, own short texts after the EGM reviewer personas; output format and isolation come from the tool); viewer gets `tag:goldfish-lens`. `diff`: only additions (all personas from viewer up gain the five skills; `nobody` and `pending-user` nothing). Matrix `skill_rows` + skill-list tests updated; `test_goldfish` runs the default lenses for a viewer and none for a user without groups |
| G3 | `user_agent` tool + instruction; chat card for `goldfish_review` | Live on localhost and the tunnel: brainstorm → draft → gate → review card → resolve → both artifacts download; lens `skill_access` audit records carry the chat's `agent_session_id`; a user with no groups sees no flow or lenses | ✅ 2026-11-07: `user_agent` gets `make_goldfish_review(MCP_URL, MODEL)` + a short instruction (follow `egm-document-flow`, review only after the user agrees); chat card `goldfish_review` (`lib/results.ts` `goldfishReview`, `components/renderers.tsx`): one line "Goldfish review · ran/N lenses" + blocker / major / nit counts, the body has lens outcomes and findings (plain text). Live check (user, 2026-11-07): brainstorm → draft → gate → review card → resolve → both artifacts saved, on localhost and the tunnel. Audit of that chat: `skill_access` allow for the flow and all four lenses, 16 `search_knowledge` calls (Elephant + reviewers), 12 `tools_list`, 2 `save_artifact`, every record under the chat's `agent_session_id` and one oid |
| G4 | Brainstorm as its own skill `egm-brainstorm` (proposed 2026-11-07; today brainstorming is only step 1 of `egm-document-flow`, guidance with no structure or gate): a fixed set of questions (goal, audience, scope / out of scope, constraints, sources to check with the knowledge tools, open questions), answered in a few turns, then a short **brief** the user confirms before any drafting. Brainstorming runs in **broad context** (no active team; G9) and quietly collects team hints (repos, projects, systems, document type) without asking about the team; the brief has a **Team** field (named in the chat → `resolve_team(hints)` with its reason → `default_team` → otherwise "which team?" answered when confirming the brief; one-team users never see a question), and confirming the brief sets the active team. `egm-document-flow` step 1 loads it and drafts from the confirmed brief; the brief stays with the Elephant (Goldfish reviewers still see only the draft) and is saved with the review as a "Brief" section of `<name>-review.md`. Usable alone for work that isn't a document. Content only: `skills/core/egm-brainstorm/SKILL.md`, `skills.yaml` (tag `general`, same grant as the flow), matrix `skill_rows`; no code, no new tool | `sdlc-config validate` + `diff` (only the new skill added, for the same personas as `egm-document-flow`); live: a document request asks the brief's questions, shows the brief, waits for "yes", then drafts; the saved review artifact contains the brief and its team; a user in two teams who mentions a payments repo gets "Team: payments (repo payments-api mentioned)" in the brief, with no separate team question | ✅ 2026-11-07 (live check passed, user): `skills/core/egm-brainstorm` (questions → **narrow the approach**: 2–3 options with trade-offs, the user picks, never silently; user's refinement 2026-11-07 → brief with Approach + Team → explicit yes; the confirmed brief ends brainstorming, starts the design stage and **locks the team** via `set_active_team` once G9 exists; `resolve_team` used when available). `egm-document-flow` step 1 loads it, step 2 applies the locked team, the review artifact gets a "Brief" section. `diff`: only `egm-brainstorm` added, viewer and up |
| G5 | The two missing EGM reviewer lenses (proposed 2026-11-07): `lens-structure` (document structure: order of sections, headings, one idea per section, missing or duplicate sections, what belongs in an appendix) and `lens-style` (technical writing: plain words, short sentences, defined terms, consistent names, no filler or hedging), own short texts after the EGM structural and style reviewer personas, like the other four. **Opt-in, not in the default set** (`goldfish.DEFAULT_LENSES` stays four, so no code change): `egm-document-flow` lists them and proposes them at the gate for long or formal documents (designs, proposals, reports) or when the user asks; 4 defaults + 2 = 6 = `MAX_LENSES`, so a review with both leaves no room for a team lens (the flow says so). Content only: `skills/core/lens-structure/`, `skills/core/lens-style/`, `skills.yaml` (tag `goldfish-lens`: viewer and up get them through the existing grant), `egm-document-flow` lens list, matrix `skill_rows` | `sdlc-config validate` + `diff` (only the two lenses added, for the personas that have the other lenses); `tests/agent/test_goldfish.py` still passes; live: a review with `lenses` including both reports findings traced to them; the default review is unchanged (four lenses) | ✅ 2026-11-07 (live check passed, user): `lens-structure`, `lens-style` (tag `goldfish-lens`, opt-in), flow lens list + the 6-lens cap note; `diff`: only the two lenses, viewer and up; config/policy/MCP/agent tests 473 passed |
| G6 | Typed team skills (layer 3): `tags` on `addons.skills` entries (team schema + resolver; only platform-listed tags; a team tag grants nothing outside the team's members, and role `access` still applies); examples `payments-pci-lens` (`goldfish-lens`) and `payments-story-questions` (`brief-questions`) in `skills/teams/payments/`; `egm-document-flow` / `egm-brainstorm` discover them by tag through `list_skills`. CODEOWNERS already covers the team folder | Config tests: an unlisted tag fails validation; a payments member sees the team lens in `list_skills`, a non-member gets "unknown skill"; `diff` shows the additions only for payments personas; live: a payments design review offers the PCI lens | ✅ 2026-11-07 (live check passed, user): `platform.yaml` `skills.team_tags` [goldfish-lens, brief-questions, doc-template]; team add-on `tags` (schema + loader: unlisted tag fails). Tags grant nothing: role `tag:` grants still match global skills only, so viewer's `tag:goldfish-lens` does not reach `payments-pci-lens` (test). `list_skills` now returns `tags` and, for add-ons, `team`. Payments examples: `payments-pci-lens`, `payments-story-questions`, `payments-design-template`; flow + brainstorm skills find them by tag for the locked team only. `diff`: the three for payments members and admin (`*`) only |
| G7 | Structured flow defaults + limits (layers 4–5): `addons.flows.document` in the team schema (refs checked against the team's visible skills), `get_agent_context` returns `flows` as data, `platform.yaml` gets the document-flow limits (`max_lenses`, `max_llm_calls_per_reviewer`, `max_rereviews`; teams may only lower), `goldfish.py` takes defaults + limits from the caller's context instead of constants, for the **team confirmed in the brief** (G9; no active team = platform defaults only); flow skill text updated for precedence and required lenses. Needs G9 | Unit tests: precedence (platform → team confirmed in the brief → user request), required lens cannot be dropped, two teams' lenses merge up to the cap and an over-cap required set is reported, template conflict asks; resolver rejects a team raising a limit; existing goldfish tests pass; `diff` shows the flow defaults per persona | ✅ 2026-11-07 (live check passed, user): `platform.yaml` `flows.document` (default lenses, `max_lenses` 6, `max_llm_calls_per_reviewer` 8, `max_rereviews` 1); team `addons.flows.document` (`lenses`, `types.<type>.template/brief/lenses/required_lenses`, caps). Loader: refs must be a global skill or the team's own add-on **with the matching tag**, team caps only lower, unknown keys fail. `sdlc_config.document_flow(snapshot, policy, team)` merges platform → team (visible skills only); `get_agent_context` returns it as `flows.document`; the prompt shows the locked team's defaults. `goldfish_review(doc_type=)` + `plan_lenses`: platform → locked team's type → user request, required lenses always added (reported as `added_required_lenses`), over-cap → error naming the required ones; code caps stay the ceiling (flow fetch failure = code defaults). **Changed by G9:** one locked team per document, so the multi-team merge and the template conflict question are not needed. Not done: `sdlc-config diff` does not show flow defaults (only permissions) |
| G9 | Active team per conversation (proposed 2026-11-07), decided **when the brief is confirmed**, not at the start. MCP: `get_agent_context(team=None)` adds a `teams` list (name + one-line purpose) and, with `team=X`, returns X in full only for a member (else "unknown team"); new read-only tool `resolve_team(hints)` matching repo / project / source names against the caller's own teams → one team, `ambiguous` + candidates, or `none` (`tools.yaml` + persona rows; audited with the team as correlation); optional `default_team` per user in `users.yaml`. Agent: local tool `set_active_team(team)` (only one of the caller's teams; written through `tool_context.state` as `sdlc_active_team`, server-side; clients cannot set it, AG-UI / A2A already strip client state); `with_team_context` renders **broad** (every team as a one-line summary + context values) without an active team and the active team **in full** (addendum, G7 defaults) plus "also a member of …" with one; the active team is part of its cache key. The team is fixed for the document (draft, review, re-review, both artifacts; recorded in `<name>-review.md`); switching later = a brief change, the agent offers to redraft. Non-document chats never set a team. Chat: "Team: X" chip in the thread header once set (a click sends an ordinary "switch to team …" message). Autonomous runs take the team from their `Trigger` (P6) | Unit tests: one-team user resolves with no question; a hint matching one team resolves with its reason; ambiguous hints ask in the brief; `set_active_team` refuses a team the caller is not in; a removed member's active team is cleared and asked again; broad vs full rendering; MCP: `get_agent_context(team=)` for a non-member answers "unknown team"; live: brainstorm shows no team-specific behaviour, the confirmed brief switches to the team's template / lenses, reopening the thread keeps the team | ✅ 2026-11-07 (live check passed, user): team `metadata.description`; users.yaml `default_team` (unknown team fails; applies only while a member). MCP `team_tools.py`: `get_agent_context(team=)` (+ `teams`, `default_team`, `flows`; non-member and unknown both "unknown team (not one of your teams)", no argument value in the error/audit) and `resolve_team(hints)` (keywords from the caller's own teams only: name, context values incl. a URL's last segment, constraint values such as repos, readable sources the team owns; one match → team + reason, several → `ambiguous`, none → only team → default team → `none` + candidates); `tools.yaml` + viewer grant + matrix rows. Agent: `make_set_active_team` (checks with `get_agent_context(team=)` as the user, writes `sdlc_active_team`; empty = clear), `with_team_context` renders broad (team list + default + all addenda kept, as guidance) or the locked team in full (its addendum, context, flow defaults, others named only), cache key includes the team; a team the user left → broad view + "settle the team again". `sdlc_web` drops client-sent `sdlc_` state keys (AG-UI state and `/run` state_delta; A2A already drops all). Chat: a `set_active_team` line "Team · payments · locked for this document" (**deviation:** a tool-result line, not a thread-header chip). Brainstorm runs broad, narrows the approach with the user, and locks the team when the brief is confirmed (the user's refinement 2026-11-07). **Restart (user, 2026-11-07):** after a document is saved the team stays locked for follow-up edits; new work in the same conversation asks "start in broad context or keep <X>?" and unlocks (`set_active_team("")`) only after the user chose broad (`egm-brainstorm`, flow step 7, `user_agent` instruction) |
| G8 | (optional) Team evals: `tests/evals/teams/<team>/` with a sample draft and the findings a team lens must raise, run like the retrieval eval (`SDLC_EVAL=1`) | The payments PCI lens flags the seeded PCI gap in its sample draft; skipped without the flag | ✅ 2026-11-07: `tests/evals/test_team_lens_eval.py` + `tests/evals/teams/payments/design_refund_retries.md` (stores and logs full card numbers, no PCI section). Live run (gemini-3.8-flash): 3 blockers (stored PAN, logged card data, CDE scope) + 1 major (missing PCI impact statement), all from `payments-pci-lens` |

**Third team `webapp` (2026-11-09, on top of G6–G9, config + content only):** team `config/teams/webapp.yaml`
(app roles `SDLC.Webapp.Developer` / `.Lead` + users.yaml, no group; repo limits on `full-stack-fastapi-template`),
source `webapp-code` (GitHub fork, tracks `master`; generated client and the fork's `.claude/` / `.agents/` excluded),
add-ons `webapp-coding-standards`, `webapp-code-review`, `webapp-api-lens` (goldfish-lens, required for designs),
`webapp-design-template` / `webapp-story-template` (doc-template). First step-by-step guide for adding a team and
for new members: `docs/guides/TEAM_ONBOARDING.md`. Pending (user): app roles in Entra (`entra_setup.ps1`), ingest,
GCP `-Step config` + `-Step ingest`.

**Fixes from the G4–G9 live test (2026-11-07):**
- *Review cancelled through the tunnel:* a Goldfish review sends no events for minutes; the Cloudflare tunnel dropped
  the silent `/run_sse` stream (~2 min idle) and the run was cancelled with the request. Fix: SSE keep-alive
  comments (`: keep-alive`, after 15 s idle) on every `text/event-stream` response of the agent app
  (`sdlc_web.keepalive.SseKeepAliveMiddleware`, outermost) and of the chat runtime to the browser
  (`ui/copilotkit/lib/keepalive.ts` in the CopilotKit route). Clients ignore comment lines (AG-UI parses `data:` only).
- *`LlmCallsLimitExceededError` (8) failed lenses:* reviewers are asked for at most 3 searches; on their last
  allowed call their tools are removed and they must answer (`_answer_on_last_call`), so a reviewer ends with
  findings, never that error; `max_llm_calls_per_reviewer` 8 → 12 (code ceiling and platform.yaml); the
  synthesizer has a 120 s limit (timeout = findings grouped without merging).

## P11 — Keyword (full-text) search (proposal, asked 2026-11-06)

**Why:** retrieval today is cosine similarity (pgvector HNSW, `search_knowledge`) plus the knowledge graph
(recursive walk over `entities` / `edges`, `graph_query`). The eval's "hybrid" is vector + graph. Nothing matches
exact tokens, and embeddings are weak on them: Jira keys (`PAY-1234`), error codes, config keys, function and file
names. The only keyword-like step is matching entity names found in the question when picking graph starting points.
Cloud SQL Postgres 17 has full-text search built in (no extension), so this needs no new infrastructure.

**Design (to confirm, Q7):**
- **Migration 007:** `chunks.content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(heading, '') || ' ' || content)) STORED`
  + GIN index. `simple` (no stemming, no stop words) keeps identifiers intact; `english` stemming is the
  alternative for prose (Q7). Ingest needs no change (generated column); RLS policies and grants are unchanged
  (same table, same rows). Adding the column rewrites `chunks` once (the dev indexes are small).
- **Query:** `websearch_to_tsquery('simple', query)` ranked by `ts_rank_cd`, run under `sdlc_db.scoped()` like the
  vector query. Identifier-friendly normalization of the query (keep `PAY-1234`, `snake_case`, dotted names as
  whole tokens as well as their parts) lives in `sdlc_db`, with unit tests.
- **Fusion:** reciprocal rank fusion (RRF, k = 60) of the vector and keyword rankings in `search_knowledge`;
  `graph_query` uses the fused list as its candidate set (graph starting points then also come from keyword hits).
  Results gain `via: "keyword"` / `"vector"` / `"both"` (and `"graph"` as today).
- **Optional, only if the eval shows a need:** `pg_trgm` for fuzzy / partial identifier matches (allowed on Cloud SQL;
  `sdlc-db bootstrap` creates the extension; no superuser needed).
- **No new tool and no new argument** at first, so no `tools.yaml` or persona-matrix changes. A `mode` argument
  (vector | keyword | hybrid) comes later only if users need to choose, and then with `tools.yaml` `args`.
- **Eval:** add exact-token questions to `tests/evals/retrieval_questions.yaml` (keys, error codes, config
  names from the sample sources) and variants `vector+fts` and `hybrid+fts` to `tests/evals/`; same metric as the
  version-02 runs, local and GCP.

**Milestones:**

| # | Scope | Exit gate | Status |
|---|---|---|---|
| K1 | Migration 007 + keyword query + RRF in `sdlc_db`, wired into `search_knowledge` and `graph_query` | `tests/db`: keyword hits only from readable sources (RLS: another team's chunk never matches), exact-token query finds its chunk where vector-only misses, fusion order is deterministic; CI passes without `.env` (HashEmbedder) | ✅ 2026-11-07: `007_chunks_fulltext.sql` (`content_tsv` generated, `simple`, GIN); `sdlc_db.knowledge`: `keyword_terms` (identifier-like terms only, see K2), `tsquery_text` (OR of quoted terms; only `[a-z0-9_./-]`), `keyword_rows` (under `scoped()`, in a savepoint: without the column = vector only + warning), `fuse` (RRF k=60); `search(query=, keyword=)` and `graph_search(keyword=)`; results carry `via` vector / keyword / both (chat: "exact match" badge). Switch `platform.yaml` `knowledge.keyword_search`. `tests/db/test_keyword_search.py` (RLS, exact token vs vector-only, determinism, graph seeds, fallback) + `test_keyword_terms.py`; DB 66 passed |
| K2 | Eval: exact-token questions + `vector+fts` / `hybrid+fts` variants | On the ingested dev DB (local, then GCP after `-Step db`): fused ≥ the current best variant overall, and better on the exact-token questions; otherwise K1 is reverted or left off | ✅ local 2026-11-07 (GCP after `-Step db`): 8 `exact: true` questions (5 samples, 3 repo), variants `vector+fts`, `hybrid h1+fts`, gate `test_keyword_fusion_gate`. First design failed the gate: plain words (≥4 letters) and equal-weight RRF made `vector+fts` lose prose questions (all recall@5 0.817 vs 0.878). **Changed:** only identifier-like terms (digits, `_ . - /`, inner capitals) are searched, and `search_knowledge` ranks by cosine + keyword rank bonus (0.08, halved by rank 11, as `graph_query`) instead of RRF; `graph_query` keeps RRF for its walk seeds. Result (41 questions): all recall@5 vector 0.951 → vector+fts **0.963** (hybrid h1 0.939 → h1+fts 0.963), MRR 0.725 → 0.747; exact token MRR 0.838 → **1.000** (recall@3 0.875 → 1.000). Cost: multi-hop MRR 0.495 → 0.449 and recall@3 0.722 → 0.667. `keyword_search: true`. The Stage 6 gate now runs on the original questions (`stage6` group). **GCP dev (2026-11-07, via Cloud SQL Auth Proxy): gate failed** for `graph_query` (hybrid h1 0.976 → h1+fts 0.951; `search_knowledge` improved as locally): plain acronyms (MCP, GCP) counted as identifiers, matched most chunks and, as equal-weight RRF walk seeds, pushed the right files out. **Fix:** plain all-caps words are no longer keyword terms (digits, `_ . - /` or camelCase still are). Local after the fix: all recall@5 h1+fts **0.976** (best variant), MRR vector+fts 0.760, multi-hop MRR 0.537 (no longer a cost), exact token MRR 1.000. **GCP re-run with the fix: both eval tests pass (user, 2026-11-07)**; deployed to GCP dev (images → plan → apply, user, 2026-11-07) |
| K3 | (only if K2 shows misses on partial identifiers) `pg_trgm` similarity as a third ranking | K2 eval improves again; bootstrap still passes on Cloud SQL | not planned |

## Open questions

| # | Question | Needed for |
|---|---|---|
| Q1 | ~~Staging: GCP project, region, hostnames, who approves applies~~ not needed: P1 dropped 2026-11-07 | — |
| Q2 | Order of P1–P9; what "done" means for version-03 | all |
| Q3 | Atlassian Cloud site and a Data Center instance for live checks? Which private repos / sources? | P8 |
| Q4 | ~~Artifacts: first use cases, storage, retention, sharing scope~~ answered 2026-11-05 (§P5 A1–A5) | P5 |
| Q5 | Agent runtimes: ~~trigger sources~~ (answered 2026-11-06, §P6 R1: Bitbucket Cloud + DC, GCP Cloud Monitoring; GitHub later), report channels (CI: Code Insights + PR comment proposed; ops: Google Chat / Teams / email?), one runtime service or one per agent. Option raised 2026-11-05: try `ci_agent` / `ops_agent` first as dev-only folders in the existing ADK web app (they run as the signed-in user, so this tests prompts, skills and report format, not workload identity or triggers) | P6, P7 |
| Q6 | Write tools: which first, and the approval model (per call, per session, per team policy) | P7 |
| Q7 | ~~Keyword search: priority, text-search configuration, graph starting points~~ answered 2026-11-07: next after P10; `simple` only; `graph_query` starts from the fused list | P11 |

## Rules that carry over

All CLAUDE.md rules stay: authorization in the MCP server only, deny by default, config-declared access, the user runs
Terraform and the deploy script, Entra changes need confirmation per action, dev shortcuts never reach staging/prod.
New for version-03: GCP environments use no client secrets (P2) and no `*.run.app` URLs (P3).
