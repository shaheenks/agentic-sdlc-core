# Agentic SDLC — Incremental Deployment Plan

Architecture diagrams and component overview: [ARCHITECTURE.md](ARCHITECTURE.md).

## Progress
| Stage | Status | Notes |
|---|---|---|
| 0 — Foundations | ✅ Done (2026-09-26) | uv workspace, ruff/pytest/pre-commit, docker compose: postgres (pgvector, 127.0.0.1:5432), mcp-bootstrap, agent-bootstrap all healthy. App role `sdlc_app` is non-superuser. Entra app registrations/groups still pending (needed for Stage 2). |
| 1 — Walking skeleton | ✅ Done (2026-09-26) | Gate passed: agent calls `list_skills` → `load_skill` and produces the user story, both on the host (`tests/e2e`) and in the agent container via adk web. Gemini `gemini-3.8-flash` on Vertex AI (`cloud-migration-agent`, location `global`) via ADC. |
| 2 — Identity + config core | 🟡 Identity gate passed; 2d built, live check pending | **Gate passed live** on the local dev tenant: paul (payments) and ana (platform) get different `whoami` groups; no/invalid token → 401; invalid config → server exits with `ConfigError`. Built: `sdlc_config` (Platform/GroupMap schemas, loader, ConfigStore, `validate`), `sdlc_auth` (EntraTokenVerifier, Principal, Graph overage fallback), MCP server (Entra auth + RFC 9728 metadata, `whoami`, JSON audit, `config_version`). Entra provisioned by `scripts/entra_setup.ps1`. **2d built:** oauth2-proxy → `sdlc-agent-web` (token re-validation, user binding, ContextVar passthrough) → agent `bearer_header_provider` → MCP. **Pending:** live browser sign-in + `tests/e2e/test_stage2_agent.py` with a real user token. |
| 3–9 | ⏳ Not started | |

## Context
Greenfield project (`c:\Users\shaheenks\pg\dev\agentic-sdlc` is empty). Goal: an agentic SDLC assistant built on Google ADK. Agents are composed from **skills**. Central **MCP server(s)** serve all skills, tools and knowledge, and enforce **user identity + RBAC with selective disclosure**. Access and team-specific behavior are driven by **declarative YAML config**, keyed on **Entra ID identity + Entra group membership**. Start small (local Docker), then grow to GCP and to more user surfaces (adk web → Gemini Enterprise → Antigravity).

### Decisions (clarified with user)
| Topic | Decision |
|---|---|
| Runtime | Local docker-compose first; production later on **GCP** |
| LLM | **Gemini** (Vertex AI / Gemini API), embeddings via Gemini embedding model |
| Identity | **Entra ID is the single IdP**; the user is identified by Entra `oid` + **Entra group membership** |
| Authorization source | Versioned **YAML config files** (groups, roles, teams, tools, skills, sources), validated by JSON Schema |
| Database | **Postgres + pgvector** (one DB for vectors, plus the graph as edge tables) |
| RBAC scope | Tool **visibility** (tools/list), tool **invocation** (per tool + args), **data-level** RAG filtering, skill visibility |
| Skills | SKILL.md-style folders. Content lives in `skills/`; access is set only in `config/` |
| Downstream calls | Service credential behind the RBAC gate (OBO deferred) |
| RAG sources (v1) | Local folders only, each declared as a `Source` config |

### Assumptions to confirm during Stage 0
- Google-account users exist in Entra (B2B guest or federated), because Entra is the single IdP. On GCP, Entra is federated into Google via **Workforce Identity Federation**.
- The `sdlc-mcp` app registration emits a `groups` claim set to **"Groups assigned to the application"**, which avoids the 200-group overage. If an overage claim still appears, the server falls back to Microsoft Graph `transitiveMemberOf` using its own app credential, cached for 10 min.
  - *Outcome (local tenant, Entra Free):* group-to-app assignment needs P1, so the local tenant uses `SecurityGroup` claims and assigns **users** to `sdlc-mcp`. `scripts/entra_setup.ps1` detects the tier and picks the variant. The Graph fallback is built and unit-tested but not configured locally (no `ENTRA_GRAPH_CLIENT_SECRET`); overage users therefore get no groups (fail closed).
  - *Outcome:* the tenant's app policy rejects custom identifier URIs such as `api://sdlc-mcp`, so the API uses `api://<client id>`. v2 tokens carry the client ID as `aud` either way; `platform.yaml` accepts both forms.
- Group object IDs differ per tenant/environment, so they appear **only** in `config/env/<env>/groups.yaml`. Every other file refers to groups by alias.

## Target Architecture
```
 User (Entra login) ── access token: oid, upn, groups[], scp=access_as_user, aud=sdlc-mcp client id (v2)
   ▼
 Surface: adk web (auth proxy) │ Gemini Enterprise │ Antigravity (direct MCP)
   ▼
 ADK Agent (root agent + skill loader + team instruction addenda) ── forwards bearer ──►
   ▼
 MCP Server(s)
   ├─ AuthN: validate Entra JWT → Principal{oid, upn, group_ids}
   ├─ Resolver (libs/sdlc_config): group_ids → aliases → teams → roles → EffectivePolicy
   ├─ Enforcement: tools/list filter, tools/call authz + arg constraints, skill filter, data scope
   ├─ Tools: whoami(explain), list_skills, load_skill, search_knowledge, graph_query, …
   └─ Audit log (oid, teams, roles, tool, args hash, decision, matched rule)
   ▼
 Postgres + pgvector — chunks/entities/edges carry source_id + classification; RLS keyed on
                       app.allowed_sources + app.max_classification
   ▲
 Ingest pipeline — reads config/sources/*.yaml → chunk → embed → extract graph → upsert
```

## Configuration Model

### File layout
```
config/
  platform.yaml              # kind: Platform: issuer/audience, defaults, classification levels
  roles.yaml                 # kind: RoleSet: permission bundles + global group→role bindings
  tools.yaml                 # kind: ToolCatalog: every tool, its server, risk, argument schema
  skills.yaml                # kind: SkillCatalog: global skills + who can use them
  teams/<team>.yaml          # kind: Team: membership (groups→roles) + team add-ons
  sources/<source-id>.yaml   # kind: Source: source artefacts, ingest settings, data access
  env/<local|dev|prod>/
    groups.yaml              # kind: GroupMap: alias → Entra group object ID (per tenant)
    platform.override.yaml   # optional per-env overrides (tenant id, URLs)
  schemas/*.schema.json      # JSON Schema per kind (validated in CI, pre-commit, and at startup)
```
Every file carries `apiVersion: sdlc/v1` and `kind:`. Loading is strict: unknown keys, unknown group aliases, tools, skills or sources, and inheritance cycles all **fail startup**.

### groups.yaml (per environment)
```yaml
apiVersion: sdlc/v1
kind: GroupMap
groups:
  eng-all:         { id: "8b1f…-uuid", description: "All engineering" }
  payments-devs:   { id: "2c4e…-uuid" }
  payments-leads:  { id: "91aa…-uuid" }
  platform-admins: { id: "d0c3…-uuid" }
```

### roles.yaml
```yaml
apiVersion: sdlc/v1
kind: RoleSet
bindings:                       # global: apply regardless of team
  - group: eng-all
    roles: [viewer]
  - group: platform-admins
    roles: [admin]
roles:
  viewer:
    tools:  { allow: [whoami, list_skills, load_skill, get_agent_context, search_knowledge] }
    skills: { allow: ["tag:general"] }
    data:   { max_classification: internal }
  developer:
    inherits: [viewer]
    tools:  { allow: [graph_query, generate_tests, review_code] }
    skills: { allow: ["tag:engineering"] }
  lead:
    inherits: [developer]
    tools:  { allow: [approve_design] }
    data:   { max_classification: confidential }
  admin:
    inherits: [lead]
    tools:  { allow: ["*"] }
    skills: { allow: ["*"] }
    data:   { max_classification: restricted, sources: ["*"] }
```

### tools.yaml
```yaml
apiVersion: sdlc/v1
kind: ToolCatalog
servers:
  bootstrap: { url: "${MCP_BOOTSTRAP_URL}" }
tools:
  search_knowledge: { server: bootstrap, risk: low,    data_scoped: true }
  graph_query:      { server: bootstrap, risk: low,    data_scoped: true }
  review_code:      { server: bootstrap, risk: medium, args: { repo: { type: string } } }
  approve_design:   { server: bootstrap, risk: high }
```
A tool that is registered in code but missing from the catalog is never exposed.

### skills.yaml (global skills)
```yaml
apiVersion: sdlc/v1
kind: SkillCatalog
skills:
  write-user-story:   { path: skills/core/write-user-story,   tags: [general] }
  test-case-gen:      { path: skills/core/test-case-gen,      tags: [engineering] }
  design-review:      { path: skills/core/design-review,      tags: [engineering], access: { roles: [lead] } }
```
Visibility is granted by role `skills.allow` (by name or `tag:`), optionally narrowed by `access`.

### teams/<team>.yaml (membership + add-ons)
```yaml
apiVersion: sdlc/v1
kind: Team
metadata:
  name: payments
  owners: [payments-leads]           # group aliases; also used for CODEOWNERS
membership:
  - group: payments-devs
    roles: [developer]
  - group: payments-leads
    roles: [lead]
policy:
  tools:
    deny: []                         # team-level denies (deny always wins)
    constraints:
      review_code:
        args:
          repo: { in: [payments-api, payments-ui] }
addons:                              # visible only to members of this team
  skills:
    pci-checklist:        { path: skills/teams/payments/pci-checklist }
    ledger-design-review: { path: skills/teams/payments/ledger-design-review, access: { roles: [lead] } }
  instructions: skills/teams/payments/AGENT_ADDENDUM.md   # appended to the agent system prompt
  context:
    default_project: payments
    glossary_source: payments-docs   # biases retrieval toward this source
```

### sources/<source-id>.yaml (source artefacts + data access)
```yaml
apiVersion: sdlc/v1
kind: Source
metadata:
  id: payments-code
  owner_team: payments
spec:
  type: local_folder                 # later: git, jira, confluence, sharepoint, gdrive
  location: /data/sources/payments-api
  include: ["**/*.py", "**/*.md", "docs/**"]
  exclude: ["**/tests/fixtures/**", "**/*.lock"]
  classification: internal           # public < internal < confidential < restricted
  ingest:
    chunking:  { strategy: code_aware, max_tokens: 800, overlap: 100 }
    embedding: { model: gemini-embedding-001, dimensions: 768 }
    graph:     { enabled: true, entity_types: [service, module, api, requirement, owner] }
    schedule:  manual                # later: cron expression
access:                              # the ONLY place that grants read access to this data
  teams: [payments]                  # all members of the team
  roles: [admin]                     # cross-team access by role
  groups: []                         # ad-hoc group aliases
```

### Resolution algorithm (libs/sdlc_config)
1. **AuthN:** validated token → `oid`, `upn`, `group_ids` (overage → Graph lookup).
2. **Groups:** map `group_ids` → aliases via `groups.yaml`. Unknown IDs are ignored.
3. **Teams:** a principal belongs to every team that has a membership entry for one of its aliases.
4. **Roles:** union of global `bindings` and team `membership` roles, expanded through `inherits`.
5. **Tools:** union of role `allow`s ∩ catalog, minus every `deny` (deny wins). Argument constraints across the principal's teams are **unioned**, because each team adds its own repos. Any tool with no constraint entry allows any value.
6. **Skills:** global skills allowed by role (and `access`), plus `addons.skills` of member teams (and `access`).
7. **Data:** `allowed_sources` = sources whose `access` matches the principal's teams, roles or groups. `max_classification` = highest level across the principal's roles. Both are set as RLS session variables on every DB transaction.
8. **Agent context:** base instructions + `addons.instructions` from member teams + merged `context`.

Output is an immutable `EffectivePolicy`, cached per `(oid, hash(group_ids), config_version)`. `whoami(explain=true)` and the CLI `sdlc-config explain --upn x@corp --env local` print the resolved teams, roles, tools, skills and sources, plus the rule behind each one.

### Governance
- Config lives in git. **CODEOWNERS:** `teams/<team>.yaml` and `sources/*` owned by that team's leads; `roles.yaml`, `tools.yaml`, `env/*/groups.yaml` owned by platform-admins.
- CI runs `sdlc-config validate --env <env>` (schema + cross-refs) and `sdlc-config diff` (effective-permission changes per persona, shown on the PR).
- Runtime delivery, reload and exposure: see **Runtime Config Exposure** below. Every audit log line records `config_version`.

## Runtime Config Exposure

### Principle
Config is **authorization data**, so it is itself subject to selective disclosure. Only MCP servers (and ingest, for `Source.spec`) read the raw config. Everyone else sees a **per-user, already-resolved view** served by the MCP server. Agents never read `config/`.

### 1. Build: git → immutable bundle
`sdlc-config compile --env <env>` runs in CI (or at local startup):
- validates schemas and cross-references (fails on any error)
- merges base files with `env/<env>/` overlays (group GUIDs, URLs)
- pre-expands role `inherits` and indexes the lookups (group GUID → alias → teams/roles)
- leaves `${SECRET}` placeholders unresolved, so the bundle never contains secrets
- outputs `bundle.json` + `manifest.json {version: <git-sha>-<content-hash>, env, created_at}`.
Referenced skill files (SKILL.md, AGENT_ADDENDUM.md) are packaged alongside, so a version pins the policy and the skill content together.

### 2. Delivery: bundle → running services
| Env | How the bundle arrives | Reload |
|---|---|---|
| local | `config/` + `skills/` bind-mounted; `ConfigStore` compiles in-process | file-watch → recompile → atomic swap |
| GCP | `gs://sdlc-config-<env>/bundles/<version>/` + a `current` pointer object | Pub/Sub notification on pointer change (poll every 60s as fallback) → download → verify hash → atomic swap |

Rules:
- **Fail closed at startup:** no valid bundle → the service stays unready (readiness probe fails).
- **Last-known-good at reload:** an invalid new bundle is rejected and logged; the old one keeps serving.
- **Rollback** = move the `current` pointer back. No redeploy.
- Secrets (`${ENTRA_TENANT_ID}`, DB creds, etc.) are resolved from env vars at load time. On Cloud Run, those env vars come from Secret Manager.
- Promotion: CI publishes the bundle to dev → run gates → the same bundle is re-compiled for prod (only the env overlay differs) → pointer flip after approval.

### 3. In-process API (`libs/sdlc_config`)
```python
store = ConfigStore.from_env()          # local folder or GCS, per SDLC_CONFIG_SOURCE
snap  = store.current()                 # immutable Snapshot; hold one per request
policy = snap.resolve(principal)        # -> EffectivePolicy (cached per oid+groups hash+version)
snap.version                            # stamped on audit logs, responses, /healthz
store.subscribe(on_change)              # e.g. clear caches, re-sync DB source registry
```
Each request takes a single snapshot, so a reload mid-request cannot mix two versions.

### 4. Consumers
| Consumer | Reads | How |
|---|---|---|
| MCP server(s) | full bundle | `ConfigStore` → `EffectivePolicy` per request; drives tools/list, tools/call, skills, RLS vars |
| ADK agent | nothing directly | per-user view via MCP: filtered `tools/list`, `list_skills`/`load_skill`, `get_agent_context` (team addenda + context) at session start |
| Ingest | `Source.spec` only | `ConfigStore` in the job; stamps `source_id` + `classification` on rows |
| Postgres | `sources` registry table only | on each version change the MCP server upserts `sources(id, classification_rank, config_version)`; RLS reads session vars `app.allowed_sources` / `app.max_classification`, which are set per transaction by `sdlc_db` |
| Surfaces (Gemini Enterprise, Antigravity) | nothing | identical per-user view, because they go through the same MCP server |

### 5. Human / admin exposure (also RBAC-gated)
| Surface | Who | Shows |
|---|---|---|
| MCP tool `whoami(explain=true)` | any user | only their own teams/roles/tools/skills/sources + the matching rule for each. Other teams are never listed. |
| MCP tool `config_explain(upn)` / `config_info()` | `admin` role (tools.yaml, risk: high) | another user's EffectivePolicy; active version, loaded-at time, last reload error |
| HTTP `/healthz`, `/readyz` | infra | `config_version`, ready = bundle loaded |
| CLI `sdlc-config explain/diff` | developers, CI | offline resolution against any env/version; persona diff on PRs |

The audit log records `config_version` + the matched rule, so every decision can be replayed with `sdlc-config explain --version <v>`.

### Stage mapping
- **Stage 2:** `ConfigStore` (local folder source), fail-closed startup, `config_version` in `/healthz` and the audit log.
- **Stage 3:** `compile` + bundle/manifest, snapshots + EffectivePolicy cache, `whoami(explain)`, `config_explain`/`config_info` admin tools.
- **Stage 4:** skill content packaged into the bundle; `get_agent_context`.
- **Stage 5:** `sources` registry sync to Postgres on version change; ingest reads `Source.spec` from the store.
- **Stage 7:** GCS bundle store + `current` pointer + Pub/Sub reload, last-known-good, rollback runbook, CI promotion.

## Enterprise Tenant Readiness
Token validation, identity and the config model are tenant-agnostic: any single Entra tenant works by
setting `ENTRA_TENANT_ID` / `ENTRA_API_CLIENT_ID` and `config/env/<env>/groups.yaml`. Signing-key
rotation is handled (JWKS cached 1 h, re-fetched on an unknown `kid`). P1/P2 tenants get assigned-group
claims automatically, and `api://<client id>` meets the default identifier-URI policy. Guest (B2B) users
work as long as they are in the mapped groups.

Known gaps for enterprise tenants, and where they are addressed:

| # | Gap | Resolution | Stage |
|---|---|---|---|
| E1 | **Group overage**: enterprise users are often in more than 200 groups; on `SecurityGroup` claims they then get no groups unless the Graph fallback is set, and that needs the `GroupMember.Read.All` app permission, which many tenants refuse | Support **Entra app roles** as an identity source next to groups: `roles` claim, no overage. Config maps app-role values to teams/roles like group aliases. Prefer P1 assigned groups otherwise | 3 |
| E2 | **Nested groups** do not inherit app assignment: users in nested groups get no token when assignment is required | Assign leaf groups, or use app roles (E1); document in ENTRA_SETUP | 3 |
| E3 | **Revocation latency**: disabled users keep access until token expiry (60–90 min; longer with CAE-capable clients); CAE claims challenges not supported | Short token lifetime policy, CAE claims-challenge support or an `oid` denylist | 9 |
| E4 | **Client secrets** (`sdlc-client`, Graph fallback): often banned or capped at 6–12 months | Certificates or **federated credentials** (Entra trusts GCP workload identity; no secret) | 7 |
| E5 | **Provisioning** by script does not fit change control | `azuread` Terraform module in `infra/` + reviewable app manifest; `entra_setup.ps1` stays for dev | 7 |
| E6 | **Azure CLI pre-authorization** is a dev shortcut, may be blocked by Conditional Access, and must not exist in prod | `entra_setup.ps1 -NoAzCliPreAuth`; off outside dev | 2d |
| E7 | **Sovereign clouds** (GCC High, China): the Graph fallback hard-codes the commercial login/Graph hosts | `identity.authority_host` / `graph_host` in `platform.yaml` | backlog |
| E8 | **Egress**: the MCP server must reach the Entra JWKS endpoint | Document the allowlist/proxy; test behind a proxy | 7 |
| E9 | **Multi-tenant** (users authenticating in their own home tenant, not as guests) is rejected by design | Allow-list of tenants if ever needed | out of scope |
| E10 | **On-prem synced groups** emitting names (`sAMAccountName`) instead of object IDs silently map to nothing | Require object IDs in ENTRA_SETUP; `whoami` flags non-GUID group values | 3 |

## Repo Layout
Each top-level area is a **collection of components**. Every area has a `bootstrap/` folder holding the small-footprint starter component; later components are added as siblings. Cross-cutting code lives in `libs/`.
```
agentic-sdlc/
  CLAUDE.md
  docs/IMPLEMENTATION_PLAN.md
  docker-compose.yml
  pyproject.toml                  # uv workspace: each component is a member
  agents/
    bootstrap/                    # minimal ADK root agent + FastAPI wrapper (token passthrough)
    <sdlc-agent-n>/
  mcp_servers/
    bootstrap/                    # FastMCP server (whoami, skills, later knowledge tools)
    <server-n>/
  ingest/
    bootstrap/                    # single CLI driven by config/sources/*.yaml
    loaders/ chunkers/ embedders/ extractors/   # later split-out components
  libs/
    sdlc_auth/                    # Entra JWT validation, Graph overage fallback, get_user_token(context)
    sdlc_config/                  # config loader, schemas, resolver → EffectivePolicy, CLI (validate/explain/diff)
    sdlc_policy/                  # enforcement helpers: tools/list filter, call authz, arg constraints
    sdlc_db/                      # Postgres/pgvector repo, RLS session helpers
  skills/
    bootstrap/                    # first trivial skill
    core/<skill>/SKILL.md         # global skills
    teams/<team>/<skill>/SKILL.md # team add-on skills (+ AGENT_ADDENDUM.md)
  config/                         # see Configuration Model
  db/
    bootstrap/                    # extensions, core tables, RLS
    migrations/
  infra/                          # Terraform (GCP)
  tests/                          # persona-matrix, config resolver, RLS, e2e, retrieval evals
```

## CLAUDE.md
Repo conventions, configuration rules and security rules live in [/CLAUDE.md](../CLAUDE.md), which is created in Stage 0 and updated every stage.

## Stages
Each stage is independently deployable and has an exit gate. New config kinds are introduced only in the stage that first needs them.

### Stage 0 — Foundations (local)
- `git init`; write **CLAUDE.md**; scaffold the layout; Python 3.12 + `uv` workspace, ruff, pytest, pre-commit.
- `docker-compose.yml`: `postgres` (pgvector, 127.0.0.1:5432), `mcp-bootstrap`, `agent-bootstrap`. Init scripts in `db/bootstrap/` enable pgvector and create the non-superuser app role.
- Entra: app **sdlc-mcp** (API, identifier `api://<client id>`, scope `access_as_user`, v2 tokens, groups claim: assigned groups on P1 / `SecurityGroup` on Free) and **sdlc-client** (web app + secret for oauth2-proxy). Security groups `sdlc-eng-all`, `sdlc-payments-devs`, `sdlc-payments-leads`, `sdlc-platform-devs`, `sdlc-platform-admins`, and test users. Provisioned idempotently by `scripts/entra_setup.ps1` (see docs/ENTRA_SETUP.md). *Done in Stage 2.*
- `.env` for secrets (git-ignored).
- **Gate:** `docker compose up` gives three healthy containers.

### Stage 1 — Walking skeleton (no auth)
- Bootstrap MCP server: `ping`, `list_skills` (reads `skills/bootstrap`). Bootstrap ADK agent via `McpToolset`; run `adk web`.
- **Gate:** agent lists and follows one skill end-to-end.

### Stage 2 — Identity + config core
- ✅ `libs/sdlc_auth`: Entra v2 JWT validation (fastmcp `JWTVerifier` + tenant/oid/user-token checks), 401 + `WWW-Authenticate`, groups extraction + Graph overage fallback.
- ✅ `libs/sdlc_config` v1: loader, JSON Schemas for `Platform` and `GroupMap`, `validate` CLI (`--dummy-env` for CI).
- ✅ `ConfigStore` (local folder source, file-watch reload; polling in Docker); fail-closed startup; last-known-good reload; `config_version` in `/healthz` and audit log.
- ✅ `whoami` returns oid, upn, group aliases, group source, config version. JSON audit log per tool call (args hashed).
- ✅ *Added:* RFC 9728 protected-resource metadata (`RemoteAuthProvider`), so the 401 points MCP clients at Entra (needed for Antigravity in Stage 8).
- ✅ **2d, token propagation (built, gate pending):** `oauth2-proxy` v7.15 (Entra OIDC, `sdlc-client`, PKCE, scope `api://<api>/access_as_user` + `offline_access`, 30 min refresh) on `localhost:4180` → `sdlc-agent-web` (`libs/sdlc_web`: ADK `get_fast_api_app` + `EntraUserBindingMiddleware`). The middleware re-validates the token, binds ADK `user_id` to `oid` (paths and `/run` bodies), puts the token in a request-scoped ContextVar (never in session state; it drops injected state tokens), and refuses `/run_live`. The agent's `McpToolset(header_provider=bearer_header_provider)` (`sdlc_auth.adk.get_user_token`). Verified in ADK 2.10: header_provider runs per call; MCP sessions and tool-list caches are keyed per header set (per user).
- ✅ Enterprise E6: `entra_setup.ps1 -NoAzCliPreAuth`.
- **Gate:** ✅ users in different groups see different `whoami` (live); ✅ no token → 401; ✅ invalid config → startup fails. **2d gate (pending live run):** a signed-in user runs the skill flow through oauth2-proxy (browser) and `tests/e2e/test_stage2_agent.py` passes with a real user token; users cannot see each other's sessions (`tests/web/test_app.py`).

### Stage 3 — RBAC from config (tools)
- Add kinds `RoleSet`, `ToolCatalog`, `Team` (membership + `policy.tools`); resolver steps 1–5; `explain` CLI; `whoami(explain=true)`.
- `libs/sdlc_policy`: filter `tools/list`, enforce `tools/call` + arg constraints, deny-wins.
- `sdlc-config compile` → bundle + manifest; per-request snapshots + EffectivePolicy cache; admin tools `config_explain(upn)` / `config_info()`.
- Persona-matrix tests (persona = set of group aliases) → expected allow/deny per tool+args; `diff` CLI in CI.
- Enterprise (E1, E2, E10): Entra **app roles** as an identity source alongside groups (a `roles` claim mapped to teams/roles in config); document leaf-group assignment; `whoami` flags non-GUID group claim values.
- **Gate:** persona matrix green; e.g. a payments dev can call `review_code(repo=payments-api)` but not `payments-ledger-core` or `approve_design`.

### Stage 4 — Skills + team add-ons
- Add `SkillCatalog` and `Team.addons` (skills, instructions, context); resolver steps 6 and 8.
- `list_skills` / `load_skill` filtered by EffectivePolicy. Agent loads skills on demand, and team instruction addenda are fetched from the server at session start (`get_agent_context` tool).
- Skill content (SKILL.md, AGENT_ADDENDUM.md) packaged into the config bundle so a version pins policy + content.
- Seed global skills (user story, test-case gen, design review) plus one payments add-on skill.
- **Gate:** payments members see `pci-checklist`, platform members don't; addendum applied only for payments.

### Stage 5 — RAG v1 + data-level RBAC
- Add kind `Source`; resolver step 7.
- Schema: `documents`/`chunks` with `source_id`, `classification`, `embedding vector(768)`, HNSW index; RLS policy `source_id = ANY(current_setting('app.allowed_sources')) AND classification_rank <= app.max_classification`.
- Ingest bootstrap CLI: `ingest run --source payments-code` reads the Source config (include/exclude, chunking, embedding).
- `search_knowledge` tool uses `sdlc_db` with the RLS context set.
- `sources` registry table synced from config on each version change; ingest reads `Source.spec` via `ConfigStore`.
- **Gate:** same query from payments vs platform users returns disjoint results; an RLS test proves an unscoped raw query returns nothing.

### Stage 6 — Knowledge graph
- `entities`/`edges` tables with `source_id` + `classification` (same RLS); extraction driven by `spec.ingest.graph`.
- `graph_query`: vector seed → 1–2 hop recursive CTE → subgraph + chunks. `context.glossary_source` biases retrieval.
- **Gate:** eval set (~20 Q&A) shows hybrid ≥ vector-only; ACL tests still green.

### Stage 7 — GCP deployment
- Terraform: Cloud Run (MCP server, agent), Cloud Run Job (ingest), Cloud SQL + pgvector, Secret Manager, Artifact Registry, Cloud Logging; Workforce Identity Federation (Entra); Vertex AI.
- Config bundles in `gs://sdlc-config-<env>/` with a `current` pointer; Pub/Sub-triggered reload (60s poll fallback); last-known-good; rollback = pointer flip.
- CI: validate → diff → test → compile + publish bundle → deploy; prod promotion by pointer flip after approval.
- Enterprise (E4, E5, E8): Entra app registrations via the `azuread` Terraform module; certificates or federated credentials (GCP workload identity) instead of client secrets; document JWKS egress.
- **Gate:** Stage 1–6 gates green on GCP dev.

### Stage 8 — Additional surfaces
- **Gemini Enterprise:** Agent Engine + OAuth authorization (Entra); token forwarded unchanged.
- **Antigravity:** direct MCP client; `/.well-known/oauth-protected-resource` → Entra; pre-registered `sdlc-client` (no DCR in Entra).
- **Gate:** the same user gets an identical EffectivePolicy (compared via `whoami(explain)`) on all three surfaces.

### Stage 9 — Expansion (backlog)
- Source types `git`, `jira`, `confluence`, `sharepoint`, with optional `access.inherit_from_source: true` to map native ACLs.
- Enterprise E3: token revocation (short lifetimes, CAE claims challenge or `oid` denylist); E7 sovereign-cloud hosts if needed.
- Entra OBO for downstream calls; OpenTelemetry; rate limits per team (`Team.policy.limits`); ADK evals in CI; OPA/Cedar if rules outgrow YAML; admin UI over config (still git-backed).

## Key Risks
- **Group claim overage / nested groups:** mitigated by assigned-groups claim + Graph fallback; app roles planned (E1). See **Enterprise Tenant Readiness**.
- **Config drift across environments:** only group IDs vary per env; `diff` on every PR.
- **Token passthrough differs per surface:** isolated in `get_user_token(context)`.
- **Entra lacks DCR:** pre-registered client for MCP clients.
- **Prompt injection in retrieved content/skills:** authorization stays server-side; team addenda are reviewed via CODEOWNERS.

## Verification
- Per-stage gates via `docker compose up` + `adk web` with each test user.
- `pytest`: JWT validation (expired/wrong aud/tenant/overage), config schema + cross-ref failures, resolver unit tests (inheritance, deny-wins, constraint union), persona matrix, RLS tests on a real Postgres container, retrieval evals.
- `sdlc-config explain` output per test user matches the expected fixtures; audit logs record the matched rule + config_version.
