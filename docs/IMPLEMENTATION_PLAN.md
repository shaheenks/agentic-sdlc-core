# Agentic SDLC — Incremental Deployment Plan

Architecture diagrams and component overview: [ARCHITECTURE.md](ARCHITECTURE.md).

## Progress
| Stage | Status | Notes |
|---|---|---|
| 0 — Foundations | ✅ Done (2026-09-26) | uv workspace, ruff/pytest/pre-commit, docker compose: postgres (pgvector, 127.0.0.1:5432), mcp-bootstrap, agent-bootstrap all healthy. App role `sdlc_app` is non-superuser. (Entra app registrations and groups were provisioned in Stage 2.) |
| 1 — Walking skeleton | ✅ Done (2026-09-26) | Gate passed: agent calls `list_skills` → `load_skill` and produces the user story, both on the host (`tests/e2e`) and in the agent container via adk web. Gemini `gemini-3.8-flash` on Vertex AI (`cloud-migration-agent`, location `global`) via ADC. |
| 2 — Identity + config core | ✅ Done (2026-09-26) | **Gates passed live** on the local dev tenant: paul (payments) and ana (platform) get different `whoami` groups; no/invalid token → 401; invalid config → server exits with `ConfigError`; both users sign in at `localhost:4180` (oauth2-proxy), run the skill flow, and the MCP audit log shows each user's own `list_skills`/`load_skill` calls; users cannot see each other's sessions. Built: `sdlc_config`, `sdlc_auth` (EntraTokenVerifier, Principal, Graph overage fallback, token passthrough), MCP server (Entra auth + RFC 9728 metadata, `whoami`, JSON audit), `sdlc_web` (token re-validation, user binding, `/dev/*` developer tools restricted). Entra provisioned by `scripts/entra_setup.ps1`. Follow-ups: oauth2-proxy server-side session store (Redis) in Stage 7; `/run_live` binding when needed. |
| 3 — RBAC from config (tools) | ✅ Done (2026-09-27) | **Gate passed live** (MCP audit log): payments dev: `review_code(payments-api)` allowed, `review_code(platform-infra)` denied by `teams/payments.yaml#policy/tools/constraints/review_code`, `approve_design` hidden; platform dev: `generate_tests(platform-ci)` allowed, `review_code(payments-api)` denied by the platform limit; admin: `config_info` / `config_explain` allowed via `roles.yaml#bindings[2]`; a user with no mapped groups gets only `ping`/`whoami` (`everyone` binding). Built: config kinds + cross-refs, resolver + cache, `sdlc_policy` + policy middleware (filter, authorize, audit with matched rule), app roles, non-GUID flag, stub SDLC tools, admin tools, `whoami(explain)`, CLI `explain`/`diff`, persona matrix. 181 tests. |
| 4 — Skills + team add-ons | ✅ Done (2026-09-27) | **Gate passed live** (MCP audit log + user checks): each session fetched its team context (`get_agent_context`); payments users (paul, payments-lead account) got the payments add-ons and instructions, platform (ana) got `infra-change-review`, admin (ben) all skills; ana's `load_skill(pci-checklist)` answered "unknown skill"; no auth failures. Built: SkillCatalog + add-ons with naming checks, resolver skills/instructions/context, per-user `list_skills`/`load_skill`, `get_agent_context`, `sdlc_agent.with_team_context`, seed skills. Audit additions after the gate: `skill_access` (allow/deny + real reason) and `skills_list` events, `request_id`, error type/details with tracebacks, `agent_session_id` conversation correlation (one MCP client session per user token + conversation). 256 tests. Note: `load_skill` is granted as a tool; hidden skills show as outcome `tool_error` in the audit, not as a policy deny. |
| 5 — RAG v1 + data-level RBAC | ✅ Done (2026-09-27) | **Gate passed live** (browser + MCP audit log): paul (payments dev) got `payments-code` + `eng-standards` results only; ana (platform dev) got `platform-infra` + `eng-standards`, disjoint from paul's; the payments-lead account also got the confidential `payments-incidents`; every `search_knowledge` call audited `allow`/`ok` with the user's teams and roles; no auth failures. Built (5a–5f): `Source` kind + resolver data step (`allowed_sources`, `max_classification`); DB roles `sdlc_owner`/`sdlc_app`/`sdlc_ingest` (none bypasses RLS); migration `001_knowledge` (`sources`/`documents`/`chunks`, `vector(768)` HNSW, RLS ENABLE + FORCE, no context = no rows); `libs/sdlc_db` (`scoped()` RLS context, search, `sdlc-db migrate`, `gemini-embedding-2` embedder); `sdlc-ingest` (markdown/code/fixed chunking, content-hash skip, `--force`), on-demand compose services `migrate` / `ingest`; MCP `search_knowledge` under RLS; sample corpus in `samples/sources/`. Verified in the containers with Vertex embeddings: payments dev -> `payments-code` (+ `eng-standards`), platform dev -> `platform-infra` + `eng-standards`, payments lead also -> confidential `payments-incidents`. 308 tests (incl. RLS on a throwaway DB and data rows in the persona matrix). Also fixed: `auth_failure` is audited before the 401/403 is sent (flaky-test race). |
| 6 — Knowledge graph | ✅ Done (2026-09-27) | **Gate passed live** (browser + MCP audit log): paul (payments dev), ana (platform dev), the payments-lead account and ben (admin) each ran `graph_query`, allowed via their developer/admin roles, with answers only from their readable sources; a user without the developer role did not see `graph_query` in tools/list. The only auth failures were expired tokens from conversations opened before the rebuild (rejected, as intended). Built (6a–6e): migration `002_graph` (`entities`/`mentions`/`edges` with source + classification and FORCE RLS; ingest-only `extraction_cache`); Gemini structured extraction per chunk (`gemini-3.8-flash`, thinking `low`, cached); per-source graph joined by entity key at query time; `graph_query` (vector seed → 1–2 hops → best chunk per document + entities/relations; team `glossary_source` boost); all four sources graph-enabled; sample corpus expanded to 24 files; graph RLS tests + persona rows + 22-question eval. Eval (live): gate met (hybrid recall@5 1.000 ≥ vector 0.985), but the graph's re-ranking itself adds nothing measurable on this corpus (the gain comes from one result per document; recall@3/MRR equal to vector+dedup). |
| 7 — GCP deployment | ⏸️ Deferred to a later phase (2026-09-27) | **Current development phase runs on localhost + Cloudflare Tunnel only**; GCP is required in later stages and resumes from here. Split into **7a deploy** (Terraform, images, Cloud Run, Cloud SQL, Secret Manager; Stage 1–6 gates on GCP) and **7b operations** (config bundles + Pub/Sub reload, `compile`, CI promotion). Decisions: env `staging` in `cloud-migration-agent` / `asia-south1`; Cloud Run `*.run.app` URLs first (custom hostnames later); staging callback added to the existing `sdlc-client`. **7a status:** built and committed (`infra/gcp` Terraform, `scripts/gcp_deploy.ps1`, `sdlc-db bootstrap`); on GCP: state bucket, APIs and Artifact Registry created; images `mcp-bootstrap`, `agent-bootstrap`, `ingest` (tag `57f55cc3ef68`) and mirrored `oauth2-proxy` pushed; staging OAuth callback registered on `sdlc-client`. **Deferred** by decision: Cloud SQL, secrets, service accounts, Cloud Run services and jobs (43 resources) not created; the saved plan was discarded. Resume: `plan` (`-ImageTag 57f55cc3ef68` or rebuilt images) → `apply` → `db` → `ingest` → Stage 1–6 gates. Design, diagrams and runbook: [GCP_DEPLOYMENT.md](GCP_DEPLOYMENT.md). |
| 8–9 | ⏳ Not started | |

### Current phase: local development backlog (while GCP is deferred)
Work that needs only localhost + the Cloudflare Tunnel, in the agreed order (analysis of 2026-09-27).

| # | Item | Status |
|---|---|---|
| H1 | Classification changes apply without re-ingest: the RLS context carries `readable_sources` (granted AND at or below the ceiling by the current config); rows keep their stamp as a second check (lowering waits for ingest: fail closed) | ✅ Done (2026-09-27) |
| H2 | E7: Entra login/Graph hosts from `platform.yaml` instead of hard-coded | ⏳ Next |
| H3 | CI on GitHub Actions: ruff, unit + DB tests (pgvector service), `sdlc-config validate`/`diff`, `terraform fmt`/`validate` | ⏳ |
| H4 | Config bundles, local part of 7b: `sdlc-config compile`, folder store with `current` pointer, last-known-good, rollback | ⏳ |
| H5 | Stage 8 Antigravity via the tunnel MCP endpoint (same `whoami(explain)` as the web UI) | ⏳ |
| H6 | CODEOWNERS for config and schemas | ⏳ |
| H7 | E8 egress docs + JWKS through an HTTPS proxy; E3 `oid` denylist | ⏳ |
| H8 | Stage 9 locally: team rate limits, OpenTelemetry, `git` source type (bigger corpus for graph ranking) | ⏳ |
| H9 | Persistent agent sessions (design: agents get no DB credentials); skill-hidden audit as policy deny; `/run_live` binding | ⏳ |

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
| Postgres | `sources` registry table only | ingest upserts `sources(id, classification_rank, config_version)` and stamps rows; the MCP server needs no writes: RLS reads session vars `app.allowed_sources` (the caller's `readable_sources`, filtered by the **current** config's classification) / `app.max_classification_rank`, set per transaction by `sdlc_db`, so a raised classification applies on the next request |
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
- **Stage 5:** `sources` registry sync to Postgres by ingest; ingest reads `Source.spec` from the store; the RLS context uses the current config's classification (`readable_sources`).
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
- ✅ *Added after live testing:* oauth2-proxy `SKIP_CLAIMS_FROM_PROFILE_URL` (the Graph profile call failed with the API-audience token); camelCase run bodies (`userId`) bound; ADK `/dev/*` developer tools restricted to the chat UI's needs (own-session traces only; builder, deploy, evals and tests refused; `SDLC_DEV_TOOLS=true` for local dev).
- **Gate:** ✅ users in different groups see different `whoami` (live); ✅ no token → 401; ✅ invalid config → startup fails. ✅ **2d (live):** paul and ana each run the skill flow through oauth2-proxy in the browser, and the MCP audit shows their own UPNs; sessions are not visible to each other. Automated: `tests/web/test_app.py` (isolation, /dev restrictions) and `tests/e2e/test_stage2_agent.py` (needs `SDLC_E2E_USER_TOKEN`).

#### Public exposure (added after Stage 2)
- **Environment rule:** development is reachable **both** on `localhost` and through the Cloudflare Tunnel. **Higher environments (staging, prod) are hosted directly**: DNS CNAME to the platform endpoint and a managed certificate, with no tunnel and no localhost callbacks. See ARCHITECTURE.md §7.
- ✅ Cloudflare Tunnel (managed in the dashboard; connector = `Cloudflared` Windows service on the host): `app-sdlc-dev.shaheenks.co.in` → `localhost:4181` (`oauth2-proxy-public`), `mcp-sdlc-dev.shaheenks.co.in` → `localhost:8080` (MCP server). Verified publicly: valid TLS, sign-in callback on the public host, MCP 401 with public metadata, and **browser sign-in + agent use by a tenant user through `app-sdlc-dev`** (2026-09-26). Public oauth2-proxy opt-in with `docker compose --profile tunnel`. Two oauth2-proxy instances share one Entra client: local (`http://localhost:4180`, fixed callback) and public (fixed HTTPS callback, `Secure` cookies, reverse-proxy mode). `MCP_PUBLIC_URL` advertises the public MCP URL in the 401 metadata. Users: tenant members assigned to `sdlc-mcp` only (no B2B guests for now). Setup: docs/CLOUDFLARE_TUNNEL.md.

### Stage 3 — RBAC from config (tools)
Decisions (2026-09-27): stub tools for the RBAC demo; add a platform team; `explain` takes personas/group aliases (UPN lookup later, with the Graph fallback); `compile` moves to Stage 7; a third test user as live admin; app roles in code + config only (no tenant changes).
- **3a Config kinds:** `RoleSet` (roles.yaml), `ToolCatalog` (tools.yaml), `Team` (teams/*.yaml, multi-file) with JSON Schemas and cross-reference checks (unknown group aliases, roles, tools and constrained args; inheritance cycles) that fail startup.
- **3b Resolver** → `EffectivePolicy` (identities → teams + bindings → roles with inherits → allowed tools − denies; argument limits unioned across the teams that constrain a tool; `unconstrained: true` roles skip them). Every grant and deny keeps its source rule. Cached per (oid, groups, app roles, config version).
- **3c Enforcement** (`libs/sdlc_policy` + MCP middleware): filter `tools/list`, authorize every `tools/call` (deny by default, deny wins, argument limits), audit `teams`, `roles`, `decision`, `matched_rule`. Tools not in the catalog are never exposed. Stub tools `review_code`, `generate_tests`, `approve_design` (clearly marked) for the demo.
- **3d Enterprise E1/E2/E10:** `roles` claim → `Principal.app_roles`; bindings and membership accept `app_role:` next to `group:`; `whoami` flags non-GUID group claims; ENTRA_SETUP notes leaf-group assignment. No tenant changes.
- **3e Explainability:** `whoami(explain=true)`; admin-only MCP tools `config_info()` and `config_explain(groups, app_roles)`; CLI `sdlc-config explain --groups …` and `sdlc-config diff` (per-persona permission changes between git revisions).
- **Audit events (added):** `sdlc.audit` also records `tools_list` (visible tools + hidden count) and `auth_failure` (rejected tokens on the MCP endpoint: reason such as `missing_token`/`expired`/`wrong_tenant`/`wrong_audience`/`missing_scope`/`invalid_token`, client IP incl. `CF-Connecting-IP`, token fingerprint, unverified claims). Verified live through the tunnel.
- **3f Persona matrix:** `tests/policy/personas.yaml` + matrix of persona × tool × args → allow/deny, in CI.
- **Gate:** ✅ passed live (2026-09-27). Persona matrix green; live: paul (payments developer) can call `review_code(repo=payments-api)` but not another team's repo or `approve_design`; ana (platform developer) gets platform repos only; the admin test user sees `config_info` / `config_explain`; a user with only `eng-all` sees just the basic tools.

### Stage 4 — Skills + team add-ons
Decisions (2026-09-27): team instructions/context are applied **automatically per session** (ADK async instruction provider calls `get_agent_context` with the user's token); skill names are **globally unique**; a **platform add-on** is added for a symmetric check; the owner's own account becomes a **payments lead** for the live check (tenant change only after explicit confirmation).
- **Skill naming strategy:** lowercase kebab-case, globally unique across `skills.yaml` and all team add-ons (validation fails on duplicates); folder name = `SKILL.md` `name` = config key; global skills in `skills/core/<name>/`, team add-ons in `skills/teams/<team>/<name>/`, team instructions in `skills/teams/<team>/AGENT_ADDENDUM.md`; add-on names domain-specific or team-prefixed when generic; names are stable IDs (rename = remove + add, reviewed with `diff`); tags lowercase kebab-case, granted as `tag:<tag>`.
- **4a Config:** `SkillCatalog` (skills.yaml) + `Team.addons`; SKILL.md frontmatter checked against the name; role `skills.allow` → known skills/tags; add-on and instruction files must exist and stay inside `skills/`. Skill and addendum content is part of the snapshot and its version.
- **4b Resolver** (steps 6 and 8): visible skills = global skills allowed by role (name, `tag:`, `*`) and narrowed by `access` (roles/teams) + member teams' add-ons (with `access`); agent instructions + context from member teams; every grant keeps its source rule.
- **4c MCP:** `list_skills` / `load_skill` filtered by the policy (hidden skills answer "unknown skill"); `get_agent_context` tool; skills no longer read from a folder at startup.
- **4d Agent:** async instruction provider appends the caller's team addenda, cached per session. Addenda are guidance, never authorization.
- **4e Seed content:** global `write-user-story` (moved to `skills/core/`), `test-case-gen`, `design-review` (leads); payments add-ons `pci-checklist`, `ledger-design-review` (leads) + addendum; platform add-on `infra-change-review` + addendum.
- **Audit (added):** `skill_access` events for every `load_skill` (allow/deny, matched rule, real reason: not a member / access roles / no role grant / not found) and `skills_list` events; all audit records carry `request_id`; failures record `error_type` + `error` (500 chars) and unexpected exceptions log a traceback to `sdlc.mcp` with the same `request_id`.
- **Correlation (added):** the agent sends the ADK conversation id (`X-SDLC-Agent-Session`) with the user token; audit records carry `agent_session_id` (+ `mcp_session_id` when a client sends one). Because ADK pools MCP client sessions by header set, this gives **one MCP session per (user token, conversation)** instead of one per user token; the MCP server side is stateless under the current protocol. See ARCHITECTURE.md §4 "Agent -> MCP connections and correlation".
- **4f Tests:** schema/cross-refs, resolver, skill rows in the persona matrix, MCP filtering + `get_agent_context`, agent instruction provider.
- **Gate:** ✅ passed live (2026-09-27). paul (payments dev) sees `pci-checklist` and the payments addendum is applied; ana (platform dev) sees `infra-change-review`, not payments content; the payments-lead account sees `ledger-design-review` and `design-review`; ben (admin) sees all skills; hidden skills answer "unknown skill".

### Stage 5 — RAG v1 + data-level RBAC
Decisions (2026-09-27): **sample corpus** in `samples/sources/` (no real data); embeddings **`gemini-embedding-2` at 768 dims** (verified on Vertex, location `global`); DB roles **`sdlc_owner`** (owns tables, migrations) / **`sdlc_app`** (read-only, MCP server) / **`sdlc_ingest`** (writes) with **FORCE ROW LEVEL SECURITY** on every data table; ingest runs as an **on-demand compose service**. Data access is granted **only** by `Source.access` (the admin role's former `data.sources: ["*"]` is removed; admins get access via `access.roles`).
- **5a Config:** `Source` kind (location relative to the repo, include/exclude globs, `classification`, ingest settings, `access` teams/roles/groups); cross-refs to teams, roles, group aliases, classification levels. Resolver step 7: `allowed_sources` (sources whose `access` matches) + `max_classification` (highest level across the user's roles; the platform default otherwise).
- **5b Database:** numbered SQL migrations in `db/migrations/` applied by `sdlc-db migrate` (tracked in `schema_migrations`); tables `sources`, `documents`, `chunks` (`embedding vector(768)`, HNSW cosine index); RLS policy on each: `source_id = ANY(current_setting('app.allowed_sources'))` and `classification_rank <= current_setting('app.max_classification_rank')`; no context = no rows.
- **5c `libs/sdlc_db`:** `scoped(conn, policy)` sets the RLS context per transaction (`SET LOCAL`); the only way the MCP server reads data. Source registry sync (config -> `sources` table) runs at the start of each ingest run.
- **5d Ingest (`ingest/bootstrap`):** `sdlc-ingest run --source <id> | --all [--dry-run] [--force]` (`docker compose run --rm ingest …`; schema via `docker compose run --rm migrate`): walk files (include/exclude), chunk (Markdown by headings, code by functions/classes, size fallback), embed (task type RETRIEVAL_DOCUMENT), upsert; unchanged files (content hash) are skipped, deleted files removed.
- **5e MCP:** `search_knowledge(query, k<=20)` under RLS: returns source, path, line range, score, snippet; audited as usual.
- **5f Tests:** RLS on a real Postgres (raw query without context -> 0 rows; per-persona visibility; classification ceiling; ingest role cannot read other than via its policy), resolver data rows in the persona matrix, chunker, ingest with a fake embedder, MCP search per persona.
- **Implementation notes:** `gemini-embedding-2` embeds one input per call (a list is silently merged into one vector), so documents are embedded per chunk in a small thread pool with a count/dimension check. Tiny sections (a lone title) merge into the next chunk so they don't outrank real content. `PGHOST=127.0.0.1` on the host: `localhost` resolves to IPv6 first and Docker publishes Postgres on IPv4 only (connections hung). psycopg async needs a `SelectorEventLoop` on Windows. The MCP server's `sdlc_app` pool opens lazily inside the server's event loop. Verified in the container with Vertex embeddings: payments dev -> `payments-code` only; platform dev -> `eng-standards` + `platform-infra`; payments lead additionally -> `payments-incidents`.
- **Gate:** ✅ passed live (2026-09-27). paul and ana get disjoint results for the same question (payments vs platform sources); both see the shared engineering standards; a payments developer (max `internal`) never sees the confidential incidents source, a payments lead does; a raw query without RLS context returns zero rows.

### Stage 6 — Knowledge graph
Decisions (2026-09-27): **Gemini structured extraction** per chunk (entity/relation types from the Source config,
results cached by chunk content); **per-source graph, joined by entity key at query time** (no global entities, so a
connection never reveals a source the caller can't read); **expanded sample corpus + recall eval** (~20 Q&A with
expected files, deterministic metrics, run live); **graph extraction on all four sources**.
- **6a Config + schema:** `platform.yaml` `knowledge.graph` (model, optional `thinking_level`, relation vocabulary);
  `Source.spec.ingest.graph` (`enabled`, `entity_types`, optional `relation_types` subset); validated at load.
  Migration `002_graph`: `entities` (unique per source + `key`), `mentions` (entity ↔ chunk), `edges` (evidence
  chunk), all with `source_id` + `classification_rank`, RLS ENABLE + FORCE, `app_read` / `ingest_all`; mentions and
  edges cascade with their chunk; `extraction_cache` is ingest-only (no `sdlc_app` grant).
- **6b Extraction (`sdlc_ingest.extract`):** one structured-output call per new chunk (JSON schema, temperature 0,
  prompt says the text is data), all changed chunks of a source in one parallel batch; output is untrusted and is
  cleaned (allowed types only, relations only between extracted entities, caps); cache key = prompt version + model +
  types + text. A failed extraction skips that file (retried next run). Orphaned entities are dropped.
- **6c `graph_query(query, k, hops)`** (developer role): vector top-20 → seeds = entities in the best 3 chunks +
  entities named in the question → walk 1–2 hops over edges by entity key (recursive CTE, capped at 40 keys) → chunks
  mentioning reached entities; rank = cosine + graph bonus by depth + glossary boost; best chunk per document; returns
  results (with `via: vector|graph`), entities and relations. Every step runs under the caller's RLS context.
- **6d Eval (`tests/evals`, opt-in `SDLC_EVAL=1`):** 22 questions (10 multi-hop) with expected files; recall@5,
  recall@3, MRR for vector (as `search_knowledge` returns it), vector+dedup, hybrid hops 1/2.
- **6e Tests:** graph RLS per persona (incl. cross-source key joins limited to readable sources), no-context = no rows,
  cache hits, failed-extraction retry, orphan cleanup, classification stamping, `graph_query` through the MCP server,
  output cleaning, config validation, persona-matrix rows.
- **Eval result (2026-09-27, live Vertex, 24 files / ~40 chunks):**

  | | vector | vector+dedup | hybrid h1 | hybrid h2 |
  |---|---|---|---|---|
  | recall@5 (all / multi-hop) | 0.985 / 0.958 | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |
  | recall@3 (all / multi-hop) | 0.939 / 0.896 | 0.939 / 0.896 | 0.939 / 0.896 | 0.939 / 0.896 |
  | MRR (all / multi-hop) | 0.775 / 0.585 | 0.779 / 0.595 | 0.778 / 0.593 | 0.778 / 0.593 |

  The gate is met, but honestly: the improvement over `search_knowledge` comes from returning one result per document,
  not from the graph ranking. The corpus is small enough that vector search already finds nearly every expected file.
  A proximity-weighted graph bonus was tried and was worse (recall@3 0.879: hub documents get over-boosted), so the
  simple depth bonus stays. What the graph adds today is the structured answer (entities, relations, e.g.
  `refund-worker runs_on job-runner`) and results the vector top-20 misses (`job-runner-restart.md` for the INC-2031
  question). Re-evaluate ranking with a larger, real corpus (Stage 9 sources) before investing in tuning.
- **Implementation notes:** `gemini-3.8-flash` with thinking `low` is ~4x faster than the default (4.5 s vs 18 s per
  chunk) with equal extraction quality; `minimal` is not supported. After changing a source's graph settings, run
  ingest with `--force` (unchanged chunks are served from the cache).
- **Gate:** ✅ passed (2026-09-27). Eval set (~20 Q&A) shows hybrid ≥ vector-only (see above); ACL tests green; live: paul (payments dev)
  and ana (platform dev) get `graph_query` answers only from their own sources, a viewer-only user has no `graph_query`.

### Stage 7 — GCP deployment
**Deferred (2026-09-27):** the current development phase stays on localhost + the Cloudflare Tunnel; the GCP design
below is kept and resumes in a later stage ([GCP_DEPLOYMENT.md](GCP_DEPLOYMENT.md)).

Decisions (2026-09-27): split into **7a deploy** and **7b operations**; environment **`staging`** in the existing
project `cloud-migration-agent`, region **`asia-south1`** (Vertex model calls stay on location `global`); endpoints
are the Cloud Run **`*.run.app`** URLs for now (a deliberate, temporary exception to the CNAME + managed certificate
rule, which returns with custom hostnames); the staging OAuth callback is **added to the existing `sdlc-client`**
registration (admin action, confirmed per change).

Org policy findings (read-only check): `iam.allowedPolicyMemberDomains` blocks `allUsers` bindings, so the public
services use Cloud Run `invoker_iam_disabled` (`run.managed.requireInvokerIam` is not enforced);
`sql.restrictAuthorizedNetworks` is enforced, which suits the design (Cloud SQL connector only, no authorized networks).

**7a Deploy** (design and runbook: [GCP_DEPLOYMENT.md](GCP_DEPLOYMENT.md); Terraform in `infra/gcp`, state in GCS; `scripts/gcp_deploy.ps1` for images, apply and jobs):
- **Services:** `sdlc-mcp` (public, stateless, scales out; Entra token validation is the gate) and `sdlc-app`
  (oauth2-proxy as the ingress container, the agent as a sidecar on localhost, so the agent is never exposed;
  max 1 instance while ADK sessions are in memory; agents still get no DB credentials).
- **Jobs:** `sdlc-db-setup` (`sdlc-db bootstrap` + `migrate`) and `sdlc-ingest` (sample corpus baked into the image).
- **Data:** Cloud SQL PostgreSQL 17 + pgvector (smallest Enterprise tier), Cloud SQL connector only; the same three
  roles and FORCE RLS as local. `sdlc-db bootstrap` replaces the Docker init script where there is no init hook and no
  true superuser (Cloud SQL `postgres` is `cloudsqlsuperuser`).
- **Identity:** one service account per workload (least privilege: Cloud SQL client, Vertex AI user, its own secrets);
  Vertex via the service identity (no ADC file). Secrets in Secret Manager (DB passwords, Entra client/graph secrets,
  cookie secret, the tenant's `groups.yaml`, mounted as a file). Tenant/app IDs come from `.env` at deploy time and
  are never committed.
- **Config:** baked into the images per release (`SDLC_ENV=staging`, no file watch); bundles and hot reload are 7b.
- **Gate (7a):** Stage 1–6 gates pass on `staging` (sign-in, per-user tools/skills/team context, `search_knowledge`
  and `graph_query` per user, audit records in Cloud Logging).

**7b Operations** (after 7a is tested):
- Workforce Identity Federation (Entra) where Google-side identity is needed; oauth2-proxy session store (Redis) and a persistent ADK session store so `sdlc-app` can scale out.
- Config bundles in `gs://sdlc-config-<env>/` with a `current` pointer; Pub/Sub-triggered reload (60s poll fallback); last-known-good; rollback = pointer flip.
- `sdlc-config compile` → immutable bundle + manifest (moved here from Stage 3).
- CI: validate → diff → test → compile + publish bundle → deploy; prod promotion by pointer flip after approval.
- Endpoints (see ARCHITECTURE.md §7): each higher environment gets its own hostnames (`<service>-sdlc-<env>.shaheenks.co.in`) via DNS **CNAME** (Cloud Run domain mapping or load balancer) and a **managed certificate**. No Cloudflare Tunnel. Its Entra client registers only that environment's HTTPS callback (no localhost, no Azure CLI pre-auth); `MCP_PUBLIC_URL` / `SDLC_APP_HOST` / `SDLC_MCP_HOST` are set per environment.
- Enterprise (E4, E5, E8): Entra app registrations via the `azuread` Terraform module; certificates or federated credentials (GCP workload identity) instead of client secrets; document JWKS egress.
- **Gate (7b):** config change promoted by bundle + pointer flip without redeploy; rollback by pointer.

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
