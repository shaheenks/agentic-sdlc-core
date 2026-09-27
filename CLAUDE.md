# Agentic SDLC

ADK-based SDLC agents composed from skills. Central MCP server(s) serve skills, tools and
knowledge, and enforce Entra ID identity + group-based RBAC defined in `config/`. Postgres +
pgvector stores embeddings and the knowledge graph. Local: docker compose. Prod: GCP.

Architecture overview: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Full staged plan: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md). Check which stage is
current before adding features, and don't build ahead of the current stage's exit gate.

## Repo structure
- `agents/<name>/`          ADK agents (`agents/bootstrap` = starter root agent)
- `mcp_servers/<name>/`     FastMCP servers, streamable HTTP (`mcp_servers/bootstrap` = starter)
- `ingest/<component>/`     RAG + KG pipeline (`ingest/bootstrap` = single CLI; loaders/chunkers/embedders/extractors later)
- `libs/sdlc_auth`          Entra JWT validation, group overage fallback, `get_user_token(context)`
- `libs/sdlc_config`        Config loader + JSON Schemas + resolver → `EffectivePolicy`; CLI validate/explain/diff
- `libs/sdlc_policy`        Enforcement: tools/list filtering, call authz, arg constraints
- `libs/sdlc_db`            Postgres/pgvector access with RLS session context
- `libs/sdlc_web`           Serves agents (ADK web app) behind oauth2-proxy: token re-validation, user binding, token passthrough
- `libs/sdlc_agent`         Agent helpers: `with_team_context` (per-session team instructions/context via `get_agent_context`, as the user)
- `skills/core/`, `skills/teams/<team>/`   SKILL.md content only (no access rules inside skills)
- `config/`                 platform, roles, tools, skills, `teams/`, `sources/`, `env/<env>/groups.yaml`, `schemas/`
- `db/bootstrap`, `db/migrations`   Schema + RLS
- `infra/`                  Terraform (GCP)
- `tests/`                  persona-matrix, resolver, RLS, e2e, retrieval evals
- `docs/`                   Implementation plan and design docs

`bootstrap/` is the starter component in each area. Add new components as siblings instead of
growing bootstrap indefinitely. Shared code goes in `libs/`, never copied between components.

## Configuration rules
- All access is declared in `config/`. Never hardcode roles, groups, tool lists or data scopes in code.
- Identity = Entra `oid` + group membership. Group object IDs appear ONLY in
  `config/env/<env>/groups.yaml`; everything else references group aliases.
- `config/env/*/groups.yaml` is git-ignored (tenant-specific). Commit only `groups.yaml.example`
  with placeholder GUIDs; never commit tenant IDs, app IDs, group IDs or test-user UPNs.
- Resolution: groups → teams (membership) + global bindings → roles (inherits) → tools/skills/sources.
  Deny wins. Arg constraints are unioned across teams. Data access is granted only by `Source.access`.
- A new tool requires: `tools.yaml` entry (with `args` for any argument a team may limit) + role/team grants +
  persona-matrix rows (`tests/policy/matrix.yaml`; a test fails if a catalog tool has no rows).
- Identities in bindings/membership: `group:` (alias), `app_role:` (Entra app role) or `everyone: true` (roles.yaml only;
  every signed-in user gets the minimal `signed-in` role: ping, whoami).
- Argument limits: unioned across the teams that constrain a tool; a team that does not constrain it never widens
  access; roles with `tools.unconstrained: true` (admin) skip limits. Deny wins over any allow.
- Rate limits: `platform.yaml` `defaults.rate_limit` (baseline) + `teams/<team>.yaml` `policy.limits` (overall and per tool);
  most generous team wins; enforced per user after authorization; audited `outcome: rate_limited` with the rule.
- A new source requires: `config/sources/<id>.yaml` with `access` + `classification`, persona-matrix `data_rows`, a CODEOWNERS rule.
  `git` sources read a pinned `ref` (full SHA), never the working tree; DB tests ingest only `local_folder` sources.
- A team add-on (skills, instructions, context) goes in `config/teams/<team>.yaml` + `skills/teams/<team>/`.
- **Skill naming** (validated at load):
  - lowercase kebab-case `^[a-z][a-z0-9-]*$`, **globally unique** across `skills.yaml` and every team's add-ons
    (a duplicate fails validation);
  - one name everywhere: folder name = `SKILL.md` frontmatter `name` = key in `skills.yaml` / `addons.skills`;
  - layout: global `skills/core/<name>/SKILL.md`; team add-on `skills/teams/<team>/<name>/SKILL.md`;
    team instructions `skills/teams/<team>/AGENT_ADDENDUM.md`;
  - team add-on names are domain-specific (`ledger-design-review`, `infra-change-review`); prefix generic ones
    with the team (`payments-release-checklist`);
  - names are stable IDs (roles, `access`, persona matrix reference them): a rename is remove + add, reviewed
    with `sdlc-config diff`. Tags are lowercase kebab-case and granted as `tag:<tag>`.
- Every config file has `apiVersion: sdlc/v1` and `kind:`; unknown keys/references must fail validation.
- Run `uv run sdlc-config validate --env local` after any config change; review `sdlc-config diff`.

## Runtime config
See "Runtime Config Exposure" in docs/IMPLEMENTATION_PLAN.md.
- Only MCP servers (full bundle) and ingest (`Source.spec`) read config. Agents and prompts never read
  `config/`; they get per-user views through MCP tools (tools/list, list_skills, get_agent_context, whoami).
- Read config only through `ConfigStore.current()`. Take one snapshot per request; never cache policy across versions.
- `sdlc-config compile --env <env> --out <root> [--activate]` produces an immutable bundle (version = git SHA +
  content hash); `sdlc-config activate <version> --root <root>` moves the `current` pointer; `SDLC_CONFIG_BUNDLES=<root>`
  makes services load bundles instead of the folder. Bundles never contain secrets (`${VAR}` stays unresolved until
  load) but do contain the tenant `groups.yaml`: keep bundle roots out of git (`.bundles/`). Dev uses the watched folder.
- Startup fails closed without a valid bundle; reload keeps the last-known-good. Rollback = move the `current` pointer.
- Viewing another user's policy (`config_explain`) is an admin-only tool; `whoami(explain)` shows only the caller's own view.

## Security rules
- Authorization lives in the MCP server, never in prompts or agent code.
- Entra is the only trusted issuer. Tokens must be v2 (iss `https://login.microsoftonline.com/<tid>/v2.0`),
  `aud` = the sdlc-mcp client ID (v2) or `api://<client id>`, `scp` contains `access_as_user` (user tokens only),
  `tid` = our tenant, plus signature (JWKS) and exp. Implemented in `sdlc_auth.entra.EntraTokenVerifier`.
- The MCP server refuses to start without valid config and `ENTRA_TENANT_ID` / `ENTRA_API_CLIENT_ID` (fail closed).
- Users whose token omits groups (overage) get no groups unless the Graph fallback secret is set.
- Block list (E3): `config/env/<env>/blocked.yaml` (kind `BlockList`, optional, git-ignored like groups.yaml) is checked by
  the MCP token verifier on every request (via `store.current()`); blocked users get 401, audited as reason `blocked`.
- Egress (E8): token validation honours `HTTPS_PROXY`/`NO_PROXY`; unreachable JWKS = every request refused (docs/ENTRA_SETUP.md §6).
- Deny-by-default. Filter tools/list AND re-check on every tools/call.
- All DB reads go through `sdlc_db` with `app.allowed_sources` + `app.max_classification` set (Postgres RLS).
- Agents forward the user's bearer token via `get_user_token(context)`; never use a service token for user calls.
- Downstream systems use service credentials only after the RBAC check passes.
- Audit to the `sdlc.audit` logger (JSON lines), one `event` per record:
  `tool_call` (oid, teams, roles, tool, args hash, decision, matched rule, outcome, config_version),
  `tools_list` (who listed tools, visible names, hidden count; hidden names are not logged),
  `skill_access` (load_skill: skill, allow/deny, matched rule and the real reason; callers only see "unknown skill"),
  `skills_list` (visible skill names, hidden count),
  `auth_failure` (401/403 on the MCP endpoint: reason from UNVERIFIED claims, client IP, token fingerprint).
  Every record carries `request_id` (one MCP request) and `agent_session_id` (the conversation, client-supplied,
  correlation only; `mcp_session_id` only when a client sends the header). Failures record `error_type` + `error` (<=500 chars); unexpected exceptions
  (fastmcp re-raises them as ToolError, the original is the cause) also log a traceback to `sdlc.mcp` with the same
  `request_id`. Never log raw tokens or argument values.
- Secrets only in `.env` (local) / Secret Manager (GCP). Never commit them.

## Environments and endpoints
See ARCHITECTURE.md §7.
- **Current phase: development only.** Everything runs on localhost + the Cloudflare Tunnel. GCP (Stage 7) is designed and
  required later, but deferred: do not create or change GCP resources unless the user asks.
- **Development** must work on **both** `localhost` (UI :4180, MCP :8080) **and** the Cloudflare Tunnel
  (`app-sdlc-dev` / `mcp-sdlc-dev.shaheenks.co.in`). Keep both oauth2-proxy instances and both Entra callbacks working;
  test changes to sign-in, cookies or URLs on both paths.
- **Higher environments** (staging, prod) are hosted directly: DNS CNAME + managed certificate, no tunnel, no localhost
  callbacks, no Azure CLI pre-authorization.
- **Staging on GCP** (Stage 7a): project `cloud-migration-agent`, region `asia-south1`, Cloud Run `*.run.app` URLs for now
  (temporary exception to the CNAME rule). Infra is Terraform in `infra/gcp`; the staging callback is on `sdlc-client`.
  Public Cloud Run services use `invoker_iam_disabled` (org policy forbids `allUsers`); Entra stays the gate.
  **Deployment is deferred to a later stage**: only the state bucket, APIs, registry and images exist; no Cloud SQL or
  Cloud Run yet. Keep `infra/gcp` valid when shared code changes (e.g. new env vars, migrations, jobs).
  Design and runbook: docs/GCP_DEPLOYMENT.md.
- Hostnames and public URLs are configuration (`SDLC_APP_HOST`, `SDLC_MCP_HOST`, `MCP_PUBLIC_URL`), never hard-coded;
  code must not assume `localhost` or a tunnel. Use `<service>-sdlc-<env>.shaheenks.co.in` (one level below the zone).
- After changing Entra redirect URIs, check each entry separately (`az ad app show … -o json`), not the joined TSV output.

## Tenant accounts
- The dev tenant has test users for sign-in, token and persona checks (payments developer, platform developer,
  admin, and the owner's own account with no sdlc groups). Their UPNs are NOT kept in the repo; pass them on the
  command line (e.g. `entra_setup.ps1 -TestUserA … -TestUserB … -AdminUser …`).
- **The tenant admin account is used only when required and confirmed by the user for that action.** Any Entra
  change (`az ad …`, Graph writes via `az rest`, `entra_setup.ps1` without `-DryRun`) needs that confirmation.
  `az` on the dev machine is usually signed in as the admin: check `az account show` before Entra commands.
  Read-only queries and `-DryRun` are fine, but say which account they run as.

## Enterprise tenants
See "Enterprise Tenant Readiness" (gaps E1–E10) in docs/IMPLEMENTATION_PLAN.md.
- Keep identity tenant-agnostic: tenant/app IDs come from env, group IDs from the git-ignored groups.yaml.
  Never hard-code login/Graph hosts in new code; take them from `platform.yaml` (`identity.authority_host`, `graph_host`;
  the agent web app and oauth2-proxy use `ENTRA_AUTHORITY_HOST`, since agents never read config).
- Don't assume the `groups` claim is present or complete (overage, nested groups, Free-tier `SecurityGroup`).
  Missing groups mean fewer permissions, never more (fail closed). App roles (Stage 3) are the enterprise path.
- Dev-only shortcuts (Azure CLI pre-authorization, client secrets, the PowerShell provisioning script) must not
  leak into prod: prod uses Terraform, certificates or federated credentials, and no Azure CLI pre-auth.

## Commands
- `uv sync --all-packages`   install every workspace member (plain `uv sync` installs only the root)
- `docker compose up -d --build --wait`   postgres (:5432), mcp-bootstrap (:8080), agent-bootstrap (internal :8000), oauth2-proxy (:4180)
- `docker compose --profile tunnel up -d --wait`   also starts `oauth2-proxy-public` on 127.0.0.1:4181. Public endpoints
  `https://app-sdlc-dev.shaheenks.co.in` (UI -> localhost:4181) and `https://mcp-sdlc-dev.shaheenks.co.in/mcp` (-> localhost:8080) go
  through the host's `Cloudflared` Windows service (tunnel + hostnames managed in the Cloudflare dashboard). Run exactly one
  connector per tunnel. See docs/CLOUDFLARE_TUNNEL.md.
  Public names are one level deep (`*-sdlc-dev.shaheenks.co.in`) so free Universal SSL covers them.
- Open **http://localhost:4180** and sign in with Entra to use the agents (dev UI at /dev-ui/). The agent port is not published.
  ADK developer tools (builder, deploy, evals, tests, other users' traces) are off; `SDLC_DEV_TOOLS=true` enables them (never outside local dev).
- DB connections use standard `PG*` env vars. Roles: `sdlc_owner` (migrations), `sdlc_app` (MCP, read-only), `sdlc_ingest`
  (writes); none bypasses RLS. Init: `db/bootstrap/README.md`. On the host use `PGHOST=127.0.0.1` (`localhost` tries IPv6
  first and hangs; Docker publishes Postgres on IPv4 only).
- `uv run --env-file .env sdlc-agent-web`   agent web app outside Docker (expects a token in `X-Forwarded-Access-Token` or `Authorization: Bearer`)
- `uv run pytest`            unit tests; e2e tests skip without the stack + Gemini creds
- `docker compose run --rm migrate`   apply `db/migrations` as `sdlc_owner` (host: `uv run --env-file .env sdlc-db migrate`)
- `docker compose run --rm ingest run --all | --source <id> [--dry-run] [--force]`   ingest `config/sources` as `sdlc_ingest`
  (profile `ingest`, never started by `up`; host: `uv run --env-file .env sdlc-ingest run --all`)
- `uv run --env-file .env pytest tests/db`   RLS/ingest/search/graph tests on a throwaway `sdlc_test` database (needs the postgres container)
- `SDLC_EVAL=1 uv run --env-file .env pytest tests/evals -s`   retrieval eval (vector vs hybrid) on the ingested dev DB, live Vertex
- `uv run --env-file .env pytest tests/e2e`   exit-gate tests (DB + pgvector; the Stage 2 agent e2e needs `SDLC_E2E_USER_TOKEN`, see docs/ENTRA_SETUP.md)
- `uv run python scripts/mcp_whoami.py --token <entra token>`   manual identity check (see docs/ENTRA_SETUP.md)
- `.\scripts\entra_setup.ps1 -TestUserA <upn> -TestUserB <upn> [-DryRun] [-WriteLocalFiles]`   idempotent Entra provisioning
  (Windows: `az` is az.cmd, so never pass inline JSON or parentheses as az args; use `--body @file`)
- Tests never read the real `config/env/local/groups.yaml`; the `config_dir` fixture swaps in a fixed test GroupMap
- `uv run ruff check . && uv run ruff format .`
- Tracing: set `OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318` in `.env`, then `docker compose --profile observability up -d`;
  Jaeger UI http://localhost:16686. One agent turn is one trace across agent, MCP server and Postgres (context travels in
  MCP `_meta`, not HTTP headers; never add a per-call trace header: it would break one MCP session per conversation).
  Spans carry no prompts, responses, tokens or argument values (agent tool args export as `{}`). Audit records carry `trace_id`.
- CI: `.github/workflows/ci.yml` (lint, config validate + PR permission diff, tests on a pgvector service after
  `sdlc-db bootstrap` + `migrate`, terraform fmt/validate). No secrets or cloud calls in CI; tests must pass without `.env`
  (placeholder Entra IDs, example GroupMap, HashEmbedder, FakeEntra).
- `uv run --env-file .env sdlc-config validate --env local` (`--dummy-env` for a structure-only check without Entra values)
- `.\scripts\gcp_deploy.ps1 -EnvName staging -Step state|base|images|plan|apply|db|ingest|urls`   GCP deployment (see
  docs/GCP_DEPLOYMENT.md). PowerShell, not bash (Windows). Commit first: images and plan use the commit SHA as tag.
  `base`/`apply` create billable resources: only with the user's go-ahead. The saved plan contains secrets (git-ignored,
  deleted by `apply`).
- `uv run --env-file .env sdlc-db bootstrap`   extension, roles, schema, grants (idempotent; no true superuser needed, as on
  Cloud SQL); fails if any role can bypass RLS. The test database is built with it.
- `uv run sdlc-config explain --persona payments-dev` | `--groups eng-all,payments-devs [--app-roles X] [--json]` (`--dummy-env` works)
- `uv run sdlc-config diff [--from HEAD] [--to WORKTREE] [--exit-code]`   per-persona permission changes (review on every config PR)
- MCP tools: `whoami(explain=true)` (own view with source rules); `list_skills` / `load_skill` (per-user; hidden skills answer
  "unknown skill"); `get_agent_context` (team instructions + context); `search_knowledge` (viewer+, vector) and
  `graph_query` (developer+, vector + knowledge graph), both under RLS; admin only: `config_info()`, `config_explain(groups, app_roles)`
- Skills: a `"*"` skill grant (admin) covers every team's add-ons; team instructions are guidance, never authorization.
  `sdlc-config diff` cannot compare across the Stage 4 boundary (older revisions lack skills.yaml) or the Stage 6 boundary
  (older revisions enable a source graph without `platform.yaml` `knowledge.graph`); later revisions diff normally.

## Workspace conventions
- uv workspace members are listed explicitly in the root `pyproject.toml`; add each new component there.
- Agent packages under `agents/` are virtual uv projects (`package = false`); `adk web agents` imports them by folder name.
- Dockerfiles build from the repo root: `docker build -f <component>/Dockerfile .`.
- ADK 2 needs the `google-adk[mcp]` extra for `McpToolset`.
- ADK calls `header_provider` only when a context is passed (`get_tools(ctx)`); agent runs always pass one, tests must too.
  MCP sessions and tool-list caches are keyed by the header hash. Agents use `agent_header_provider` (user token +
  `X-SDLC-Agent-Session` conversation id), so there is **one MCP client session per (user token, conversation)**.
  Never add per-turn values (e.g. invocation id) as headers: that would create a new MCP session every turn.
  The MCP server side is stateless (no `Mcp-Session-Id` in the current protocol).
- Gemini runs on Vertex AI via gcloud ADC (project `cloud-migration-agent`, location `global`, model `gemini-3.8-flash`). ADC has no quota project, so `.env` sets `GOOGLE_CLOUD_QUOTA_PROJECT`. The agent container gets only the ADC file, mounted at `/secrets/adc.json`.
- Python 3.12 (`.python-version`); ruff formats code only, not markdown snippets.
- Agent conversations: `SDLC_SESSION_SERVICE_URI` (compose: SQLite on the agent-only `agent-sessions` volume, 7-day
  retention). Options and trade-offs (Postgres, MCP session API, Agent Engine): ARCHITECTURE.md "Conversation storage".
- Only MCP servers and ingest get DB credentials. Agent containers get an explicit env allow-list, never the whole `.env`.
- Tests: `--import-mode=importlib` + `pythonpath=["."]`; shared helpers live in `tests/support/` (e.g. `FakeEntra` mints
  Entra-shaped RS256 tokens), fixtures in `tests/conftest.py`. MCP server tests run a real uvicorn server in a thread.
- Data tables need `source_id` + `classification_rank`, RLS ENABLE + FORCE, policies for `sdlc_app` and `sdlc_ingest`,
  and tests in `tests/db`. All reads go through `sdlc_db.scoped()`; migrations are append-only (checksummed).
- Knowledge graph: entities/edges are per source and join by `key` (`sdlc_db.entity_key`) at query time, never
  across sources at write time. Extraction output is untrusted (`Extraction.cleaned`). Bump
  `sdlc_ingest.extract.PROMPT_VERSION` when the prompt or schema changes (it invalidates the cache); run ingest with
  `--force` after changing a source's graph settings. Graph extraction uses thinking `low` (`minimal` is unsupported).
- `gemini-embedding-2` accepts one input per call (a list is silently merged); `sdlc_db.GeminiEmbedder` handles this.
  psycopg async needs a `SelectorEventLoop` on Windows (CLIs, test server and pytest already set it).
- CODEOWNERS (`.github/CODEOWNERS`): a new team, team skill folder or source needs its own rule (a test enforces it).
- New config kinds: add a JSON Schema in `config/schemas/` and register the kind in `sdlc_config/loader.py` (`_KINDS`).
