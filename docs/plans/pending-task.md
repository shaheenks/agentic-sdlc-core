# Pending tasks

Work that is agreed but not scheduled. Each task says what it waits for; when it is picked up, it moves into the
current plan ([version-02.md](version-02.md)) or a new numbered plan.

| # | Task | Waits for | Recorded |
|---|---|---|---|
| 1 | [Agent runtimes: user, CI and ops agents](#task-1--agent-runtimes-user-ci-and-ops-agents) | Trigger sources decided | 2026-11-03 |
| 2 | [Re-ingest and remove data of dropped sources](#task-2--re-ingest-and-remove-data-of-dropped-sources) | Local done; GCP dev ingest after deploy | 2026-11-03 |
| 3 | [Agent-generated artifacts: storage and access](#task-3--agent-generated-artifacts-storage-and-access) | Version-03 (decided 2026-11-05); use cases and storage still open | 2026-11-04 |

## Task 1 — Agent runtimes: user, CI and ops agents

**Status:** pending, not scheduled (recorded 2026-11-03). Nothing here is built. Revisit when the trigger sources are
decided; then move it into a numbered plan (version-03) with milestones and exit gates.

Related: [version-02.md](version-02.md) (current plan; write tools = decision D5), [../ARCHITECTURE.md](../ARCHITECTURE.md)
§4–5 (request flow, identity model).

### 1. Goal

Three agent runtimes instead of one:

| Runtime | Agent | Serves | Identity on MCP calls |
|---|---|---|---|
| interactive | `user_agent` | People, in the chat app (renamed from `bootstrap`, 2026-11-03) | The signed-in user's Entra token (unchanged) |
| autonomous | `ci_agent` | Triggers from CI workflows (pull requests, failed builds) | Its own workload identity (Entra service principal) |
| autonomous | `ops_agent` | Triggers from operational alerts | Its own workload identity (Entra service principal) |

**Decided (2026-11-03):**
- Autonomous agents use their **own workload identity** (app-only tokens with an app role), never a user's token.
  A CI run can't securely carry the pusher's user token, and alerts have no user at all.
- First version is **read and report back**: read-only MCP tools, then post the result to where the trigger came
  from. No changes to other systems (write tools stay decision D5).

**Not decided:** which trigger sources come first (§5), report channels, and the other questions in §11.

### 2. What exists today

- One agent, [agents/user_agent/agent.py](../../agents/user_agent/agent.py) (renamed from `bootstrap`; the MCP server is now `mcp_servers/core_mcp`): ADK `Agent` + `McpToolset` with
  `agent_header_provider` (user token + conversation id), served by `libs/sdlc_web` (`create_app` →
  `get_fast_api_app(agents_dir=...)`) behind oauth2-proxy; `EntraUserBindingMiddleware` binds sessions to the token `oid`.
- The MCP token verifier (`sdlc_auth.entra.EntraTokenVerifier.load_access_token`) **rejects app-only tokens**
  (`idtyp == "app"` or no `scp`).
- Config already supports `app_role:` identities (roles.yaml bindings, team membership) and `Principal.app_roles`
  is already parsed, so the resolver needs no new identity kind for service principals.
- `sdlc_agent.with_team_context` fetches team instructions as the user; autonomous agents need a per-agent version.

### 3. Layout

```
agents/
  interactive/user_agent/      today's agents/user_agent, moved one level down; served by sdlc_web as now
  autonomous/ci_agent/         headless; served by the autonomous runtime
  autonomous/ops_agent/
libs/sdlc_runner/              autonomous runtime: trigger endpoints, queue, run loop, reporters
```

- Each runtime gets its own `agents_dir`, so the chat app can never load an autonomous agent and the autonomous
  runtime has no chat UI, no oauth2-proxy and no user sessions.
- Shared helpers stay in `libs/sdlc_agent` (instruction building, result formatting); prompts live with each agent.
- Open: one runtime service hosting both autonomous agents, or one service each (§11).

### 4. Identity (workload identity)

**Entra (admin action, needs confirmation):** one app registration / service principal per autonomous agent
(`sdlc-ci-agent`, `sdlc-ops-agent`), each assigned an app role on `sdlc-mcp` (`SDLC.Agent.CI`, `SDLC.Agent.Ops`).
Credentials are **federated** from the agent's GCP service account (no client secrets on GCP). Local dev may use a
dev-only secret or certificate in `.env` (must not leak into prod, as with other dev shortcuts).

**Agent → MCP:** an app-only token from client credentials, through a new `sdlc_auth` `service_header_provider`
(token cache, refresh before expiry, run id as `X-SDLC-Agent-Session`). User agents never get this path; autonomous
agents never get user tokens.

**MCP verifier:** accept an app-only token **only** if its `roles` contain an app role listed in config
(`platform.yaml identity.service_principals.allowed_app_roles`); tid, iss, aud, oid, signature and expiry checks stay;
the block list applies to service principal oids (kill switch). `Principal` gains `kind: user | service`.

**Config:**
- `roles.yaml`: bindings `app_role: SDLC.Agent.CI → ci-agent`, `app_role: SDLC.Agent.Ops → ops-agent`. Roles get
  read-only tools only (`list_skills`, `load_skill`, `get_agent_context`, `search_knowledge`, `graph_query`, review
  skills) and their own `max_classification`.
- Data: `Source.access.roles: [ci-agent]` / `[ops-agent]` per source, like any other grant.
- Team scoping for CI (which repos a run may look at): per-trigger constraints (§5) or `teams/<team>.yaml`
  `membership: app_role: ...`. Open (§11).
- Validation rule: a tool with `credentials.user` (users' own PAT connections) is never granted to a role bound
  to a service app role.
- Persona matrix: personas `ci-agent` and `ops-agent` (app roles only) with tool, skill and data rows.

**Audit:** records gain `principal_kind: service`, `app_id`, `trigger_id`, `run_id`; `agent_session_id` = run id.

### 5. Triggers (pluggable adapters; sources not decided)

```
caller ──► POST /triggers/<adapter> ──► verify caller ──► TriggerEvent ──► queue ──► agent run ──► reporter
                                      (per adapter)    (normalised)         202 + run id
```

- `TriggerEvent`: `kind` (ci | ops), adapter, source (repo / service), ref, a size-capped payload summary, event id,
  correlation id.
- Caller authentication per adapter; prefer OIDC over shared secrets:

  | Candidate source | Caller check |
  |---|---|
  | GitHub Actions | GitHub OIDC token: issuer, audience, `repository` / `workflow` claims checked against config |
  | Bitbucket Pipelines | Bitbucket OIDC token: issuer, audience, repository / workspace claims |
  | GCP Cloud Monitoring | Alert → Pub/Sub → authenticated push: Google-signed OIDC token from the expected service account |
  | Alertmanager, PagerDuty, others | Generic webhook with HMAC signature; secret via `sdlc_secrets` |

- New config kind **`Trigger`** (`config/triggers/<id>.yaml`): adapter, accepted callers (repos / workflows /
  service accounts), target agent, repo/service constraints, report channel, rate limit, dedupe window, `enabled`.
  Needs a JSON Schema, `_KINDS` registration, tests and a CODEOWNERS rule, like sources.
- Payloads are **untrusted input** (prompt injection): passed to the agent as data, size-capped, never used
  verbatim as tool arguments.

### 6. Execution model

- Asynchronous: the endpoint returns `202 + run id`; a queue (Cloud Tasks or Pub/Sub on GCP, in-process locally)
  starts one agent run per event.
- Idempotent by event id + dedupe window (CI retries, alert re-fires).
- Limits per run: timeout, maximum tool calls, model token budget; concurrency limit per agent.
- Sessions in the same store as the chat (SQLite locally, Agent Engine on GCP) with a short TTL; a run record
  (status, timings, outcome) for operators.

### 7. Reporting back (the only write in v1)

- One reporter per adapter: PR comment or check-run summary (CI), alert annotation or chat/webhook message (ops).
- Posting uses a **service credential scoped to reporting only** (e.g. a GitHub App with `pull_requests: write` /
  `checks: write`), referenced through `sdlc_secrets`, host in `knowledge.allowed_hosts`, sent through
  `sdlc_connectors.http.HttpClient`.
- Everything else stays read-only.

### 8. Security and guardrails

- Deny by default for service principals: only app roles listed in config are accepted, only bound roles' tools.
- No user connections (PATs) for autonomous agents; classification ceiling per agent role.
- Per-trigger repo/service constraints and rate limits; full audit of every run and tool call.
- Kill switch: block-list entry for the agent's service principal oid, or `Trigger.enabled: false`.
- Evals: prompt-injection payloads (malicious PR descriptions, alert text) must not change what the agent does.

### 9. Deployment

- Local: compose services `agent-ci`, `agent-ops` (profile `autonomous`, not started by `up`).
- GCP: Cloud Run service(s) with their own service accounts and federated Entra credentials; public ingress only
  for adapters that need it (GitHub/Bitbucket), Pub/Sub push otherwise. Terraform, run by the user.

### 10. Milestones (proposal)

| # | Scope | Exit gate |
|---|---|---|
| A1 | Identity: verifier accepts allowed app-only tokens, `Principal.kind`, config rules, `service_header_provider`, persona matrix | An app-only test token gets exactly the ci-agent role's tools and sources; an app token without an allowed role gets 401 |
| A2 | Autonomous runtime + first CI adapter + reporter; move `agents/user_agent` → `agents/interactive/user_agent` | A CI trigger produces a report on a test PR; audit shows the run end to end |
| A3 | First ops adapter + reporter | A test alert produces an annotation/message |
| A4 | GCP: services, federated credentials, Terraform | Both flows work on GCP dev |
| A5 | Guardrails and evals (injection, limits, dedupe) | Eval suite passes; limits enforced |

### 11. Open questions

1. Trigger sources for v1: GitHub Actions, Bitbucket Pipelines, GCP Cloud Monitoring (Pub/Sub), Alertmanager /
   PagerDuty webhooks?
2. Report channels: PR comments vs check runs; ops: alert annotation, Google Chat / Slack / Teams?
3. CI team scoping: map repo → team in the `Trigger`, or bind the CI app role into teams?
4. One autonomous runtime service or one per agent?
5. ~~Rename `bootstrap` to `user_agent`~~: done 2026-11-03 (with `mcp_servers/bootstrap` → `core_mcp`); see version-02 §14.
6. Write actions (open issues, re-run pipelines, roll back): decision D5; would need approval gates.

## Task 2 — Re-ingest and remove data of dropped sources

**Status:** local dev DB done (2026-11-03, after N14); **GCP dev open** (step 5). Recorded 2026-11-03.

**Local run (2026-11-03):** `docker compose --profile ingest build ingest` (the compose image predated the gcs
loader: `no loader for source type 'gcs'`), then `docker compose run --rm ingest run --all --force`:
`platform-infra` removed by the registry sync; eng-standards 6 files / 11 chunks, payments-code 9 / 18,
payments-incidents 2 / 6 (all three from the config store bucket), sdlc-platform 181 files / 1012 chunks from GitHub
`main` `a9608c0` (4 stale files deleted); 653 extraction calls, no errors.

**Why:** config changes never touch the database, and ingest only runs for sources that are in config. After N12 the
local dev DB (checked 2026-11-03) still holds:

| Source | In config | Stored | Readable by |
|---|---|---|---|
| `sdlc-platform` | yes, now GitHub `agentic-sdlc-core` `main` | 134 docs, 599 chunks, 813 entities from this repo's pinned commit `f2178f0` (local, 2026-10-06), `owner_team: platform` | sdlc-platform team, admin (stale content, no GitHub links) |
| `platform-infra` | removed | 8 docs, 10 chunks, 29 entities | nobody (in no policy; RLS hides it) |
| `eng-standards`, `payments-*` | unchanged | as ingested 2026-10-06 (`owner_team` of eng-standards still `platform`) | as configured |

**Steps:**
1. Finish the source changes in `config/sources/` and run `uv run --env-file .env sdlc-config validate --env local`.
2. Data of sources no longer in config: already handled. Every non-dry-run ingest syncs the source registry
   (`sdlc_db.knowledge.sync_sources`) and deletes sources missing from config, cascading to their documents, chunks
   and graph rows (log: `source registry synced: N sources, removed [...]`). No prune command is needed.
3. Re-ingest everything: `uv run --env-file .env sdlc-ingest run --all`. `sdlc-platform` does a full read from GitHub
   (location changed: 181 files at `main`), replaces the old copy and gets GitHub deep links; graph extraction costs
   about one Gemini call per changed chunk. Use `--force` for sources whose graph settings changed.
4. Check: per-source counts, `owner_team` updated, a `graph_query` as a sdlc-platform member (e.g. Paul, users.yaml)
   returns GitHub links, and `platform-infra` is gone.
5. GCP dev: same steps with `gcp_deploy.ps1 -Step ingest` (run by the user) after the config is deployed.
6. Retrieval eval: `sdlc-platform` now tracks `main`; update `tests/evals/retrieval_questions.yaml` paths (e.g.
   `core_mcp`, `user_agent`) once version-02 is merged to GitHub `main`, then re-run `SDLC_EVAL=1 ... pytest tests/evals`.

## Task 3 — Agent-generated artifacts: storage and access

**Status:** pending, not scheduled (recorded 2026-11-04). Nothing here is built. Revisit when the first use cases
and the storage choice are decided; then move it into the current or a new numbered plan.

Related: [../ARCHITECTURE.md](../ARCHITECTURE.md) ("Conversation storage"), Task 1 (autonomous agents would produce
reports too), [version-02.md](version-02.md) decision D5 (write tools).

### 1. Goal

Let agents produce files that outlive the chat reply: generated test files, design or review documents, user
stories exported as Markdown, reports. Users can list, download and share them under the same RBAC as everything
else.

### 2. What exists today

- The agent produces **chat text only**. `agents/user_agent` saves no artifacts and nothing writes files.
- ADK's artifact service is **in memory**: `libs/sdlc_web/src/sdlc_web/app.py` passes `artifact_service_uri="memory://"`,
  `use_local_storage=False`. Anything saved would be lost on restart and not shared across Cloud Run instances.
- `generate_tests`, `review_code`, `approve_design` (`mcp_servers/core_mcp/.../sdlc_tools.py`) are stubs and store nothing.
- Generated text survives only as session events in the conversation store (SQLite on the `agent-sessions` volume
  locally, 7-day idle retention; Agent Engine sessions on GCP), bound to the user's `oid`. It is not in Postgres
  and never reachable through `search_knowledge`.
- The chat app stores nothing (`PassThroughAgentRunner`).

### 3. Design sketch (proposal)

- **Write through MCP, not the ADK artifact service.** Authorization lives in the MCP server, so artifacts are saved
  and read through MCP tools (e.g. `save_artifact`, `list_artifacts`, `get_artifact`), each in `tools.yaml` with role
  grants and persona-matrix rows. The ADK artifact service stays in memory (or off) so it can't become a second,
  unaudited store.
- **Storage:** object store for content (GCS bucket on GCP, a compose volume or local folder in dev) behind one
  `libs/` interface; metadata in Postgres (owner `oid`, team, conversation id, name, media type, size, hash,
  classification, created/expires) with RLS like the knowledge tables.
- **Access:** owner-only by default. Sharing with the owner's team is an explicit choice. Classification defaults to
  the highest classification among the sources the agent read in that conversation, so a summary of confidential
  incidents can't be read by someone below that ceiling.
- **Download:** an authenticated endpoint behind oauth2-proxy (like `/connections/`), or short-lived signed URLs
  issued only after the policy check. The chat app shows artifacts as links, never inline data from other users.
- **Limits:** max size per file and per user, allowed media types, retention (TTL) and deletion, per-user rate limit.
- **Audit:** `artifact_change` (create/delete/share) and `artifact_access` (read/download) with oid, artifact id,
  classification, decision; never the content.
- **Untrusted content:** artifacts may embed retrieved or provider content; served as downloads with a safe
  `Content-Type` and `Content-Disposition: attachment`, never rendered as HTML on our origin.

### 4. Milestones (proposal)

| # | Scope | Exit gate |
|---|---|---|
| F1 | Storage interface + metadata table (RLS, migration, `tests/db`) + MCP tools + config/persona rows | A user saves and reads back their own artifact; another user gets "not found"; audit records both |
| F2 | Download endpoint + chat app links | Download works on localhost and the Cloudflare Tunnel; no access without a valid session |
| F3 | Team sharing + classification inheritance | A shared artifact is readable by teammates at or above its classification, by nobody else |
| F4 | GCP: bucket, service account access, retention (Terraform, run by the user) | Same gates on GCP dev |

### 5. Open questions

1. First use cases: which outputs need to be files (generated tests, design docs, review reports)?
2. Storage: GCS + Postgres metadata (proposed), Postgres only for small files, or ADK's `gs://` artifact service with
   an MCP check in front?
3. Retention: tie to the conversation's TTL or keep independently?
4. Sharing scope: owner only, team, or per-artifact access lists?
5. Should artifacts ever be ingested into the knowledge base (as a source), and with what review?
6. Autonomous agents (Task 1): do their reports become artifacts owned by the service principal?
