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
| P4 | A2UI citation cards in `/chat/` + A2A endpoint (§P4, started 2026-11-06) | N7 spike (version-02 §10 "Spike findings") | U1–U6 confirmed |
| P5 | Artifacts: store, list and download agent-generated files under RBAC | pending task 3 | Q4 (use cases, storage) |
| P6 | Agent runtimes: `ci_agent`, `ops_agent` with workload identity, read + report back | pending task 1, D7 | Q5 (trigger sources, report channels) |
| P7 | Write tools on behalf of the user (create issue, comment, PR) with UI confirmation | N6, D5 | P6 decisions (approval gates) |
| P8 | Connectors and sources: Atlassian Cloud live checks (incl. AG-UI gate 5 Jira part), Data Center editions (Bitbucket DC "who am I"), Cloud + DC side by side, URL elicitation, PDF OCR live check (a source with scanned PDFs), source secrets in Secret Manager (first private source), SharePoint / Office documents, GitHub App tokens, `inherit_from_source` | N2, N6 | Q3 (Atlassian site, DC instance, private sources) |
| P9 | Quality and tooling: ADK evals in CI, retrieval ranking (re-ranker, query entities), `explain` by UPN, Antigravity OAuth sign-in + Stage 8 gate, OBO where providers support it, OPA/Cedar if rules outgrow YAML, admin UI over config | N6, version-00 Stage 8/9 | — |
| P10 | EGM document flow: full-context agent drafts, isolated Goldfish reviewers critique, user approves (§P10) | user request 2026-11-05 | P5 F2 live check |
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
| C3 | A2A server: `google-adk[a2a]`, `to_a2a(...)` mounted at `/a2a` in `sdlc_web` behind the Entra middleware, a call-context builder from the verified `oid`, A2UI as `DataPart` (`application/json+a2ui`), agent card at `/.well-known/agent-card.json` | Tests (FakeEntra): no token → 401; a valid user gets an answer with the A2UI DataPart; another user's context id → refused; no token in persisted session events; client state stripped | waits for C1 |
| C4 | Local A2A access: oauth2-proxy route for `/a2a` with bearer tokens (both proxies), a small `scripts/a2a_client.py` | A local A2A client with your Entra token gets the same answer and cards as the chat; without a token 401 | waits for C3 |
| C5 | GCP: deploy, decide exposure (U6), audit + trace checks | The same A2A call works against GCP dev; audit records carry the A2A context as `agent_session_id`; no prompt content in Cloud Trace | waits for C4 |

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
| G1 | `goldfish.py` + conversation-id ContextVar | `tests/agent/test_goldfish.py` (stub LLM). A reviewer sees no parent history and empty state; MCP calls carry the user token and the parent conversation id; a hidden lens is reported `unavailable`; the lens cap holds; synthesizer output is validated | waits for P5 F2 |
| G2 | Flow + lens skills, `skills.yaml`, viewer grant, `skill_rows` | `sdlc-config validate` + `diff` reviewed; policy/config tests pass | waits for G1 |
| G3 | `user_agent` tool + instruction; chat card for `goldfish_review` | Live on localhost and the tunnel: brainstorm → draft → gate → review card → resolve → both artifacts download; lens `skill_access` audit records carry the chat's `agent_session_id`; a user with no groups sees no flow or lenses | waits for G2 |

## Open questions

| # | Question | Needed for |
|---|---|---|
| Q1 | Staging: GCP project, region, hostnames (`<service>-sdlc-staging.shaheenks.co.in`), who approves applies | P1, P3 |
| Q2 | Order of P1–P9; what "done" means for version-03 | all |
| Q3 | Atlassian Cloud site and a Data Center instance for live checks? Which private repos / sources? | P8 |
| Q4 | ~~Artifacts: first use cases, storage, retention, sharing scope~~ answered 2026-11-05 (§P5 A1–A5) | P5 |
| Q5 | Agent runtimes: trigger sources (GitHub Actions, Bitbucket Pipelines, Cloud Monitoring, webhooks), report channels. Option raised 2026-11-05: try `ci_agent` / `ops_agent` first as dev-only folders in the existing ADK web app (they run as the signed-in user, so this tests prompts, skills and report format, not workload identity or triggers) | P6, P7 |
| Q6 | Write tools: which first, and the approval model (per call, per session, per team policy) | P7 |

## Rules that carry over

All CLAUDE.md rules stay: authorization in the MCP server only, deny by default, config-declared access, the user runs
Terraform and the deploy script, Entra changes need confirmation per action, dev shortcuts never reach staging/prod.
New for version-03: staging and prod use no client secrets in `.env` (P2) and no `*.run.app` URLs (P3).
