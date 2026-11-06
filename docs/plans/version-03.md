# Agentic SDLC — Implementation Plan version-03 (draft)

**Status: current (2026-11-05).** Version-02 closed 2026-11-06 (§20 H6, the first scheduled runs, passed).
First milestone: **P5 artifacts** (§P5): **done 2026-11-06** (F1, F2, F4, F5, F6; F3 sharing deferred).
Other milestones remain a proposal, confirmed one by one.

Follows [version-02.md](version-02.md). Architecture: [../ARCHITECTURE.md](../ARCHITECTURE.md); GCP runbook:
[../GCP_DEPLOYMENT.md](../GCP_DEPLOYMENT.md); secrets: [../SECRETS_REVIEW.md](../SECRETS_REVIEW.md); designs carried in:
[pending-task.md](pending-task.md) (tasks 1 and 3).

## Goals

1. **Production-shaped GCP:** a staging environment without dev shortcuts, enterprise identity (app roles,
   federated credentials, Entra apps in Terraform), custom hostnames, CI deploys.
2. **Richer agent output:** A2UI citation cards and an A2A endpoint (the GO from the version-02 N7 spike), and
   stored artifacts users can download.
3. **Autonomous agents:** CI and ops agents with their own workload identity, read + report back.
4. **More sources and connectors,** live-checked: Atlassian Cloud, Data Center editions, private repos.

## Milestones (proposal)

| # | Milestone | From | Waits for |
|---|---|---|---|
| P0 | Carry-in: anything from version-02 §20 that failed and was moved here | version-02 §20 | version-02 close-out |
| P1 | Staging environment | N5, D4 | Q1 (project, region, hostnames); billing go-ahead |
| P2 | Enterprise identity: app roles defined in the tenant (E1), federated credentials instead of client secrets (E4), Entra apps in Terraform (E5), no Azure CLI pre-auth outside dev (E6), per-environment Entra client | N5, version-00 E1/E4–E6, SECRETS_REVIEW §6 | Entra admin, confirmed per change |
| P3 | Operations: custom hostnames + managed certificates (drop the `*.run.app` exception), CI deploy stages (build → plan → apply with approval), Cloud SQL private IP, scale out `sdlc-app`, shared rate-limit store (if `sdlc-mcp` > 1 instance), log-based metrics + alerts on audit events, Secret Manager data-access logs | N5, N4, SECRETS_REVIEW §6 | P1 for staging parts |
| P4 | A2UI citation cards in `/chat/` + A2A endpoint (§P4, ✅ done 2026-11-06: C1–C5, live on GCP dev) | N7 spike (version-02 §10 "Spike findings") | U1–U6 confirmed |
| P5 | Artifacts: store, list and download agent-generated files under RBAC | pending task 3 | Q4 (use cases, storage) |
| P6 | Agent runtimes: `ci_agent`, `ops_agent` with workload identity, read + report back; event intake through one gateway + Pub/Sub (§P6, intake designed 2026-11-06) | pending task 1, D7 | Q5 (ops report channel; runtime layout), Q3 (Bitbucket DC instance) |
| P7 | Write tools on behalf of the user (create issue, comment, PR) with UI confirmation | N6, D5 | P6 decisions (approval gates) |
| P8 | Connectors and sources: Atlassian Cloud live checks (incl. AG-UI gate 5 Jira part), Data Center editions (Bitbucket DC "who am I"), Cloud + DC side by side, URL elicitation, PDF OCR live check (a source with scanned PDFs), source secrets in Secret Manager (first private source), SharePoint / Office documents, GitHub App tokens, `inherit_from_source` | N2, N6 | Q3 (Atlassian site, DC instance, private sources) |
| P9 | Quality and tooling: ADK evals in CI, retrieval ranking (re-ranker, query entities), `explain` by UPN, Antigravity OAuth sign-in + Stage 8 gate, OBO where providers support it, OPA/Cedar if rules outgrow YAML, admin UI over config | N6, version-00 Stage 8/9 | — |
| P10 | EGM document flow: full-context agent drafts, isolated Goldfish reviewers critique, user approves (§P10, ✅ done 2026-11-07 locally: G1–G3; GCP with the next deploy) | user request 2026-11-05 | P5 F2 live check |
| P11 | Keyword (full-text) search next to vector + graph retrieval: Postgres `tsvector` + GIN on `chunks`, fused with the vector ranking; kept only if the retrieval eval improves (§P11) | user request 2026-11-06 | Q7 |
| — | Per-source Entra group `infra-readers` (or a real one) in the tenant | N9 | a source that needs its own group |
| — | Gemini Enterprise registration (A2A agent + OAuth authorization) | version-02 §7 | org admin, workforce pool, licences; P4 |

**Order (decided 2026-11-05):** P5 first (Q4 answered). Then proposed: P4 (no outside dependencies) → P1 + P2
(staging with enterprise identity from day one) → P3 → P6 / P7 as their decisions land; P8 and P9 by priority.

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

**Milestones:**

| # | Scope | Exit gate | Status |
|---|---|---|---|
| G1 | `goldfish.py` + conversation-id ContextVar | `tests/agent/test_goldfish.py` (stub LLM). A reviewer sees no parent history and empty state; MCP calls carry the user token and the parent conversation id; a hidden lens is reported `unavailable`; the lens cap holds; synthesizer output is validated | ✅ 2026-11-06: `libs/sdlc_agent/src/sdlc_agent/goldfish.py` (`make_goldfish_review(mcp_url, model)` → FunctionTool), `sdlc_auth.adk.set_conversation_id`; `tests/agent/test_goldfish.py` (7, scripted model + real test MCP server). As built: the **tool** loads each lens with `load_skill` as the user (one MCP session, audited `skill_access`) and puts its text in the reviewer's instruction (one model call less per reviewer, the lens is always applied; a denied lens never starts a reviewer); reviewers get only `search_knowledge` / `graph_query` (filtered), their own MCP session each, `max_llm_calls` 8, 240 s timeout; unusable output = lens `failed`, never the whole review. Synthesizer: merged severity = the highest it cites, unknown or reused ids dropped, uncited findings kept; unusable output = grouped without merging. Result: `lenses` (ok / unavailable / failed), `counts`, `findings` by severity (each with `lenses` + `sources`), `summary`, `report_markdown`. `list_skills` has no tags, so the lens list is explicit (default the four `lens-*`); any skill the user can load works as a lens |
| G2 | Flow + lens skills, `skills.yaml`, viewer grant, `skill_rows` | `sdlc-config validate` + `diff` reviewed; policy/config tests pass | ✅ 2026-11-06: `skills/core/egm-document-flow` (tag `general`: brainstorm → draft → gate → `goldfish_review` → PROPOSE FIX / CONTEST, only approved edits, one re-review at most → save `<name>.md` + `<name>-review.md`) and the four `lens-*` (tag `goldfish-lens`, own short texts after the EGM reviewer personas; output format and isolation come from the tool); viewer gets `tag:goldfish-lens`. `diff`: only additions (all personas from viewer up gain the five skills; `nobody` and `pending-user` nothing). Matrix `skill_rows` + skill-list tests updated; `test_goldfish` runs the default lenses for a viewer and none for a user without groups |
| G3 | `user_agent` tool + instruction; chat card for `goldfish_review` | Live on localhost and the tunnel: brainstorm → draft → gate → review card → resolve → both artifacts download; lens `skill_access` audit records carry the chat's `agent_session_id`; a user with no groups sees no flow or lenses | ✅ 2026-11-07: `user_agent` gets `make_goldfish_review(MCP_URL, MODEL)` + a short instruction (follow `egm-document-flow`, review only after the user agrees); chat card `goldfish_review` (`lib/results.ts` `goldfishReview`, `components/renderers.tsx`): one line "Goldfish review · ran/N lenses" + blocker / major / nit counts, the body has lens outcomes and findings (plain text). Live check (user, 2026-11-07): brainstorm → draft → gate → review card → resolve → both artifacts saved, on localhost and the tunnel. Audit of that chat: `skill_access` allow for the flow and all four lenses, 16 `search_knowledge` calls (Elephant + reviewers), 12 `tools_list`, 2 `save_artifact`, every record under the chat's `agent_session_id` and one oid |

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
| K1 | Migration 007 + keyword query + RRF in `sdlc_db`, wired into `search_knowledge` and `graph_query` | `tests/db`: keyword hits only from readable sources (RLS: another team's chunk never matches), exact-token query finds its chunk where vector-only misses, fusion order is deterministic; CI passes without `.env` (HashEmbedder) | proposed |
| K2 | Eval: exact-token questions + `vector+fts` / `hybrid+fts` variants | On the ingested dev DB (local, then GCP after `-Step db`): fused ≥ the current best variant overall, and better on the exact-token questions; otherwise K1 is reverted or left off | proposed |
| K3 | (only if K2 shows misses on partial identifiers) `pg_trgm` similarity as a third ranking | K2 eval improves again; bootstrap still passes on Cloud SQL | not planned |

## Open questions

| # | Question | Needed for |
|---|---|---|
| Q1 | Staging: GCP project, region, hostnames (`<service>-sdlc-staging.shaheenks.co.in`), who approves applies | P1, P3 |
| Q2 | Order of P1–P9; what "done" means for version-03 | all |
| Q3 | Atlassian Cloud site and a Data Center instance for live checks? Which private repos / sources? | P8 |
| Q4 | ~~Artifacts: first use cases, storage, retention, sharing scope~~ answered 2026-11-05 (§P5 A1–A5) | P5 |
| Q5 | Agent runtimes: ~~trigger sources~~ (answered 2026-11-06, §P6 R1: Bitbucket Cloud + DC, GCP Cloud Monitoring; GitHub later), report channels (CI: Code Insights + PR comment proposed; ops: Google Chat / Teams / email?), one runtime service or one per agent. Option raised 2026-11-05: try `ci_agent` / `ops_agent` first as dev-only folders in the existing ADK web app (they run as the signed-in user, so this tests prompts, skills and report format, not workload identity or triggers) | P6, P7 |
| Q6 | Write tools: which first, and the approval model (per call, per session, per team policy) | P7 |
| Q7 | Keyword search: priority against P4 / P1; text-search configuration (`simple` for identifiers vs `english` stemming, or both columns); does `graph_query` also take keyword hits as starting points | P11 |

## Rules that carry over

All CLAUDE.md rules stay: authorization in the MCP server only, deny by default, config-declared access, the user runs
Terraform and the deploy script, Entra changes need confirmation per action, dev shortcuts never reach staging/prod.
New for version-03: staging and prod use no client secrets in `.env` (P2) and no `*.run.app` URLs (P3).
