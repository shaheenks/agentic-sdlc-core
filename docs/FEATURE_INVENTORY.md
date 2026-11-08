# Feature Inventory (reconciliation baseline)

Snapshot of `agentic-sdlc-core` on branch `version-03` (commit `da33d14`, 2026-11-08), built from the code, `config/`
and the plans ([version-00](plans/version-00.md) … [version-03](plans/version-03.md)). Use it to reconcile what the
plans and [ARCHITECTURE.md](ARCHITECTURE.md) claim against what the code does.

**Status legend**

| Mark | Meaning |
|---|---|
| ✅ Live | Built, tested, and checked on GCP dev (and localhost + tunnel) |
| 🟢 Built | Built and tested locally (unit / DB / fake APIs); no live or GCP check yet |
| ⚪ Stub | Exists in the catalog and is enforced, but does no real work |
| 📝 Planned | Designed or proposed in version-03; nothing built |
| ⏸ Parked | Decided not to do now |

Plan references in brackets: Stage N (version-00), M/H (version-01 / version-00 backlog), N (version-02), P/C/F/G/K/E (version-03).

---

## Part 1 — Platform capabilities

| # | Capability | What it means for users | Status |
|---|---|---|---|
| 1 | **Selective disclosure** | Each user sees only the tools, skills and knowledge their Entra groups / app roles / direct membership allow | ✅ Live |
| 2 | **Config-declared access** | All access in `config/` YAML (roles, teams, tools, skills, sources); validated, diffed per persona, reviewed via CODEOWNERS | ✅ Live |
| 3 | **Single enforcement point** | The MCP server authenticates, filters, authorizes, rate-limits and audits every call; agents make no decisions | ✅ Live |
| 4 | **Data-level security** | Postgres RLS by readable source + classification ceiling; fail closed for every DB role | ✅ Live |
| 5 | **Team knowledge (RAG)** | Vector + keyword search over ingested sources, with citations (file, lines, PDF pages, deep links) | ✅ Live |
| 6 | **Knowledge graph** | Per-source entities and relations, walked at query time under RLS | ✅ Live |
| 7 | **Skills** | Reusable SKILL.md instruction packages, global and per team, served per user | ✅ Live |
| 8 | **Team customization** | Team instructions, add-on skills, typed skills (lenses, brief questions, templates), document-flow defaults; behaviour only, never permissions | ✅ Live |
| 9 | **EGM document flow** | Brainstorm → confirmed brief (locks the team) → draft → isolated Goldfish reviewers → resolve → save document + review | ✅ Live |
| 10 | **Artifacts** | Agent-saved documents, owner only, versioned, downloadable, reviewable in the chat with line comments | ✅ Live (team sharing 📝) |
| 11 | **Act as the user** | Users connect their own GitHub / Bitbucket / Atlassian PATs; tools call those systems as the user after the policy check | ✅ Live for GitHub + Bitbucket Cloud; 🟢 Atlassian + Data Center |
| 12 | **Multiple surfaces** | CopilotKit chat (AG-UI), ADK dev UI, A2A endpoint (Gemini Enterprise), direct MCP (Antigravity) | ✅ Live (Antigravity: dev token only) |
| 13 | **Conversation history** | Per-user chat history with replay and delete | ✅ Live |
| 14 | **Audit + tracing** | JSON audit for every decision; one trace per agent turn across agent → MCP → Postgres; no prompts or tokens in spans | ✅ Live |
| 15 | **Config lifecycle** | Immutable bundles (git SHA + hash), last-known-good reload, rollback by pointer, GCS store polled on GCP | ✅ Live |
| 16 | **Revocation** | Block list (401 on next request), reconcile job for stale PATs | ✅ Live |
| 17 | **Deployment** | Docker Compose locally (+ Cloudflare Tunnel); Terraform on GCP dev (Cloud Run, Cloud SQL, Agent Engine, GCS, Secret Manager, Scheduler) | ✅ Live (dev only; staging dropped) |
| 18 | **SDLC actions** (review code, generate tests, approve design) | Tools exist to prove RBAC and argument limits | ⚪ Stub |
| 19 | **Autonomous agents** (CI / ops) + event intake | Webhook / alert-driven agents with workload identity, read + report back | 📝 Planned (P6) |
| 20 | **Write tools** (create issue, comment, PR) with UI confirmation | — | 📝 Planned (P7) |

---

## Part 2 — Features by component

### 2.1 Agent — `agents/user_agent`

| Feature | Status | Ref |
|---|---|---|
| ADK root agent on Gemini (`gemini-3.8-flash`, Vertex AI) | ✅ Live | Stage 1 |
| MCP toolset with the user's bearer token + conversation id header (one MCP session per user × conversation) | ✅ Live | Stage 2 |
| Per-session team context (`with_team_context`): broad view, or the locked team in full | ✅ Live | Stage 4, G9 |
| Local tool `goldfish_review` (EGM reviewers) | ✅ Live | G1–G3 |
| Local tool `set_active_team` (checked with MCP as the user; server-side state key) | ✅ Live | G9 |
| A2UI cards attached to tool results for A2A clients (model never sees them; forged cards dropped) | ✅ Live | C1–C2 |
| Agent links saved artifacts in answers | ✅ Live | F2 |
| `ci_agent`, `ops_agent` | 📝 Planned | P6 |

### 2.2 MCP server — `mcp_servers/core_mcp`

**Tools** (catalog `config/tools.yaml`)

| Tool | Who (default) | Status | Ref |
|---|---|---|---|
| `ping`, `whoami(explain)` | every signed-in user | ✅ Live | Stage 2 |
| `list_skills`, `load_skill` (returns tags + team; hidden = "unknown skill") | viewer+ | ✅ Live | Stage 4, G6 |
| `get_agent_context(team=)` (instructions, context, teams, default team, flow defaults) | viewer+ | ✅ Live | Stage 4, G7, G9 |
| `resolve_team(hints)` (caller's own teams only) | viewer+ | ✅ Live | G9 |
| `search_knowledge` (vector + identifier keyword bonus, `via` vector/keyword/both) | viewer+ | ✅ Live | Stage 5, K1–K2 |
| `graph_query` (vector + keyword seeds via RRF, 1–2 hop walk) | viewer+ | ✅ Live | Stage 6, N9, K1 |
| `save_artifact` / `list_artifacts` / `read_artifact(numbered, version)` / `delete_artifact` | viewer+ | ✅ Live | F1, F6 |
| `jira_get_issue`, `confluence_get_page` (user's Atlassian PAT) | per config | 🟢 Built (no live Atlassian site) | M6 |
| `github_get_file`, `bitbucket_get_file` (user's PAT, `repo` arg limits) | per config | ✅ Live (Cloud); 🟢 Bitbucket DC | M6 |
| `config_info`, `config_explain(groups, app_roles)` | admin | ✅ Live | Stage 3 |
| `review_code`, `generate_tests`, `approve_design` (`repo` arg limits) | developer / lead | ⚪ Stub (echo inputs) | Stage 3 |
| `claim_event` (event dedupe for runtimes) | service roles | 📝 Planned | P6 E3 |

**Server features**

| Feature | Status | Ref |
|---|---|---|
| Entra v2 token validation (issuer, aud, `scp`, `tid`, JWKS, exp); fail-closed startup | ✅ Live | Stage 2 |
| `tools/list` filtering + per-call re-authorization incl. argument limits | ✅ Live | Stage 3 |
| Per-user rate limits (platform baseline + team limits, per tool) | ✅ Live (in-memory; shared store 📝 P3) | H8 |
| Block list check on every request | ✅ Live | H7, N3 |
| Audit events: `tool_call`, `tools_list`, `skill_access`, `skills_list`, `artifact_change`, `artifact_access`, `connection_change`, `auth_failure` (+ `request_id`, `agent_session_id`, `trace_id`) | ✅ Live | Stage 3, N4 |
| `/connections/` API (list, add, remove PATs; expiry warning ≤ 14 days) | ✅ Live | M6, M8 |
| `/artifacts/` API (list, download as attachment, versions, DELETE with `X-SDLC-Request`) | ✅ Live | F2, F6 |
| `sdlc-reconcile-connections` CLI / job (dry run by default) | ✅ Live (dry run checked) | N3 |
| OpenTelemetry (Jaeger locally, Cloud Trace on GCP) | ✅ Live | H8, N4 |
| App-only (workload) tokens, `Principal.kind` | 📝 Planned | P6 A1 |

### 2.3 Shared libraries — `libs/`

| Library | Key features | Status |
|---|---|---|
| `sdlc_auth` | `EntraTokenVerifier`; app roles (`roles` claim); overage → no groups (Graph fallback present but **off**); `agent_header_provider`; conversation-id ContextVar for nested reviewer sessions; HTTPS proxy for JWKS | ✅ Live |
| `sdlc_config` | Loader + JSON Schemas (10 kinds); resolver → `EffectivePolicy` (groups/app roles/users.yaml → teams → roles → tools/skills/sources); document-flow merge; bundles (`compile`/`activate`/`bundles`); `ConfigStore` (file watch or bucket polling); CLI `validate` (`--check-secrets`), `explain` (`--persona/--groups/--app-roles/--user`), `diff`, `users sync` | ✅ Live |
| `sdlc_policy` | Enforcement, argument constraints, rate limiter | ✅ Live |
| `sdlc_db` | `scoped()` RLS context, `owner_scoped()` for artifacts; vector, keyword (`tsvector`), RRF fusion, graph walk; Gemini embedder (one input per call) + HashEmbedder for CI; `sdlc-db bootstrap` / `migrate` | ✅ Live |
| `sdlc_connectors` | `HttpClient` (host allowlist on every request + redirect); providers (Cloud vs Data Center); per-user secret store (file / Secret Manager); connection service; Jira/ADF text conversion; reconcile | ✅ Live (Cloud); 🟢 DC |
| `sdlc_secrets` | `{env: X}` / `{secret: x}` references, Secret Manager REST, 5-min cache | ✅ Live |
| `sdlc_artifacts` | Content store `file://` / `gs://`, limits (text only, 1 MiB, 50 per user, name rules), retention | ✅ Live |
| `sdlc_web` | Agent web app behind oauth2-proxy; token re-validation + user binding to `oid`; AG-UI `/agui`; A2A `/a2a` (A2A 0.3, owner-checked tasks/contexts) + public agent card; `/threads` list/delete; client `sdlc_`/`temp:`/`app:`/`user:` state stripped; SSE keep-alive; session retention (SQLite) / Agent Engine TTL; dev tools off unless `SDLC_DEV_TOOLS` | ✅ Live |
| `sdlc_agent` | `with_team_context`, `set_active_team`, `goldfish_review` (parallel isolated reviewers, synthesizer → Blocker/Major/Nit), A2UI card builder (strict v0.9 validation) | ✅ Live |
| `sdlc_events`, `sdlc_runner` | CloudEvents, adapter verifiers, Pub/Sub publisher; runtime consumer | 📝 Planned (P6) |

### 2.4 Ingest — `ingest/`

| Feature | Status | Ref |
|---|---|---|
| Pipeline + CLI `sdlc-ingest run --all / --source [--dry-run] [--force]`; skips unchanged content by hash; removes data of dropped sources | ✅ Live | Stage 5, task 2 |
| Loader `local_folder` | ✅ Live (tests + local) | Stage 5 |
| Loader `git` — pinned SHA or tracked branch, incremental `git diff`, deep links; GitHub | ✅ Live | H8, M1, N12 |
| Loader `git` — Bitbucket Cloud / Data Center remotes | 🟢 Built | M1 |
| Loader `gcs` (changed generations only, deletions) | ✅ Live | M2, N14 |
| Loader `confluence` (Cloud + DC, CQL, restricted pages skipped + deleted) | 🟢 Built (fake APIs) | M3 |
| Loader `jira` (Cloud + DC, JQL, issue security skipped + deleted) | 🟢 Built (fake APIs) | M4 |
| Chunking: Markdown by headings, Python/Terraform by definitions, line windows otherwise | ✅ Live | Stage 5 |
| PDFs: text layer (pypdf), page ranges, bookmarks; Gemini OCR opt-in per source (cached) | ✅ text layer; 🟢 OCR (live check P8) | H10 |
| Embeddings `gemini-embedding-2` (768 dims) | ✅ Live | Stage 5 |
| Graph extraction (Gemini structured output, types per source, cached, untrusted output cleaned) | ✅ Live | Stage 6 |
| Scheduled ingest on GCP (Cloud Scheduler → Cloud Run Job) | ✅ Live | N1, H6 |
| `ingest/chunkers`, `ingest/embedders`, `ingest/extractors` as separate components | 📝 README placeholders only (code lives in `ingest/bootstrap`) | Stage 9 |
| SharePoint / Office documents, `inherit_from_source`, GitHub App tokens | 📝 Planned | P8 |

### 2.5 Database — `db/`

| Feature | Status |
|---|---|
| Schema `sdlc`: sources, documents, chunks (HNSW cosine, iterative scan), entities, mentions, edges, artifacts (+ versions), full-text `content_tsv` + GIN (migrations 001–007, append-only, checksummed) | ✅ Live |
| RLS ENABLE + FORCE on all data tables; roles `sdlc_owner` / `sdlc_app` (read-only except its own artifact rows) / `sdlc_ingest`; bootstrap fails if any role can bypass RLS | ✅ Live |
| `agent_runs` table (event dedupe, run records) | 📝 Planned (P6) |

### 2.6 Chat app — `ui/copilotkit`

| Feature | Status | Ref |
|---|---|---|
| CopilotKit (Next.js) chat at `/chat/`, AG-UI to `/agui`; only `X-Forwarded-Access-Token` forwarded; no server-side conversation storage | ✅ Live | M5 |
| Compact renderers: citation chips (with "exact match" badge), whoami line, connected-tool cards, artifact cards, Goldfish review card, team-lock line | ✅ Live | N8, F2, G3, G9, K1 |
| History sidebar (list, open with replay, delete) | ✅ Live | N15 |
| Navbar: user + PAT status; Connections page | ✅ Live | M6, N8 |
| Artifacts panel (list, download, delete) | ✅ Live | F2 |
| Artifact viewer: numbered lines + Markdown preview, inline line comments, "Attach to chat", version picker (older versions read-only) | ✅ Live (review fixes: live recheck open) | F5, F6 |
| SSE keep-alive for long runs through the tunnel | ✅ Live | P10 fixes |
| Thread-header "Team: X" chip | Deviation: shown as a tool-result line instead | G9 |
| A2UI rendering in the chat | Not used by decision (chat keeps its own renderers) | C2 |

### 2.7 Skills — `skills/`

| Skill | Scope | Status |
|---|---|---|
| `write-user-story`, `test-case-gen` | global | ✅ Live |
| `design-review` | global, lead+ (overlaps with the lenses; "stays for now") | ✅ Live |
| `egm-document-flow`, `egm-brainstorm` | global, viewer+ | ✅ Live |
| Lenses `lens-zoom-out`, `lens-comprehension`, `lens-design-critic`, `lens-implementation-readiness` (default) + `lens-structure`, `lens-style` (opt-in) | global, `tag:goldfish-lens` | ✅ Live |
| payments: `pci-checklist`, `ledger-design-review` (lead), `payments-pci-lens`, `payments-story-questions`, `payments-design-template`, `AGENT_ADDENDUM.md`, flow defaults | team | ✅ Live |
| sdlc-platform: `infra-change-review`, `AGENT_ADDENDUM.md` | team | ✅ Live |
| webapp (2026-11-09): `webapp-coding-standards`, `webapp-code-review`, `webapp-api-lens`, `webapp-design-template`, `webapp-story-template`, `AGENT_ADDENDUM.md`, flow defaults; source `webapp-code` (GitHub, `master`); guide `docs/TEAM_ONBOARDING.md` | team | 📝 In repo (needs app roles in Entra, ingest, `-Step config` on GCP) |
| Team lens eval (`tests/evals/teams/payments`) | eval | ✅ Run live once (G8) |

### 2.8 Configuration — `config/`

| Feature | Status |
|---|---|
| Kinds: Platform, RoleSet, ToolCatalog, SkillCatalog, Team, Source, ConnectionCatalog, GroupMap, UserMap, BlockList (`apiVersion: sdlc/v1`, unknown keys fail) | ✅ Live |
| Roles `signed-in` → `viewer` (internal) → `developer` → `lead` (confidential) → `admin` (restricted, unconstrained) | ✅ Live |
| Teams `payments` (groups + app roles), `sdlc-platform` (app roles + users.yaml) | ✅ Live |
| Sources `eng-standards` (public), `payments-code` (internal), `payments-incidents` (confidential) on GCS; `sdlc-platform` (git, tracks `main`) | ✅ Live |
| Connections `github`, `bitbucket`, `atlassian` (Cloud); DC examples commented out | ✅ / 🟢 |
| App roles `SDLC.User`, `SDLC.Admin`, `SDLC.Payments.*`, `SDLC.Platform.*` | ✅ Live (E1) |
| `Trigger` kind | 📝 Planned (P6) |

### 2.9 Infrastructure and operations — `infra/gcp`, compose, CI

| Feature | Status | Ref |
|---|---|---|
| Docker Compose: postgres, core-mcp, user-agent, oauth2-proxy (:4180), `oauth2-proxy-public` (tunnel profile), migrate, ingest, Jaeger (observability profile) | ✅ Live | Stage 0–9 |
| Cloudflare Tunnel for `app-` / `mcp-sdlc-dev.shaheenks.co.in` | ✅ Live | Stage 2 |
| GCP dev: Cloud Run `sdlc-app` (oauth2-proxy + agent + chat sidecars), `sdlc-mcp`; Cloud SQL PG17 + pgvector; jobs db-setup / ingest / reconcile; Scheduler; Agent Engine sessions; GCS (config store, artifacts, source buckets); Secret Manager; Cloud Trace | ✅ Live | M7, M8, N1–N4, N13, F4 |
| `gcp_deploy.ps1` steps state/base/config/images/plan/apply/db/ingest/urls (run by the user) | ✅ Live | M7 |
| CI: ruff, config validate + PR permission diff, UI typecheck/test/build, tests on pgvector, terraform fmt/validate | ✅ Live | H3 |
| `entra_setup.ps1` (idempotent Entra provisioning incl. app roles) | ✅ Live | Stage 2, E1 |
| Custom hostnames + managed certs, CI deploy stages, Cloud SQL private IP, scale-out `sdlc-app`, alerts on audit events | 📝 Planned | P3 |
| Federated credentials (E4), Entra apps in Terraform (E5), no Azure CLI pre-auth (E6) | ⏸ Parked | P2 |
| Staging / prod environments | ⏸ Dropped for version-03 (folders `config/env/staging`, `prod`, `staging.tfvars` still exist) | P1 |

---

## Part 3 — Gaps found while compiling this (for the reconciliation)

| # | Item | Where |
|---|---|---|
| 1 | `review_code`, `generate_tests`, `approve_design` are stubs (docs now say so; real implementations not planned yet) | [sdlc_tools.py](../mcp_servers/core_mcp/src/sdlc_core_mcp/sdlc_tools.py) |
| 2 | ~~ARCHITECTURE.md said `search_knowledge` "stays vector-only"~~ fixed 2026-11-08 (keyword search section added) | ARCHITECTURE.md §5 |
| 3 | ~~ARCHITECTURE.md §6 / §8 described config as "Pub/Sub reload" / "baked into the image"~~ fixed 2026-11-08 (GCS bundle, polled) | ARCHITECTURE.md §6, §8 |
| 4 | ~~ARCHITECTURE.md §8 listed Cloud Trace as planned and identity as WIF~~ fixed 2026-11-08 | ARCHITECTURE.md §8 |
| 5 | ~~ARCHITECTURE.md §2–3 centred adk web~~ fixed 2026-11-08 (chat, A2A, artifacts, EGM flow sections added); component and GCP READMEs updated the same day | ARCHITECTURE.md §2–5 |
| 6 | Connectors never checked live: Jira/Confluence (Cloud and DC), Bitbucket DC, Bitbucket git source, PDF OCR | version-03 P8, Q3 |
| 7 | Placeholder component folders with no code: `ingest/chunkers`, `ingest/embedders`, `ingest/extractors` | `ingest/` |
| 8 | Open decisions: artifact versions vs the 50-artifact limit; renaming on a new version; F6 review fixes need a live recheck | version-03 F6 |
| 9 | `sdlc-config diff` shows permissions only, not team flow defaults | version-03 G7 |
| 10 | A2A task/context owner maps are per instance (works today at 1 instance; breaks with scale-out) | version-03 C5 |
| 11 | Rate limits are in memory per MCP instance (shared store needed if `sdlc-mcp` scales out) | version-03 P3 |
| 12 | Graph overage fallback code still present though turned off; `GroupMember.Read.All` may still be granted | version-03 P2 |
| 13 | `design-review` skill overlaps with the Goldfish lenses | version-03 P10 |
