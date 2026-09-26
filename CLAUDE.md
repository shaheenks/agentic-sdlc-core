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
- A new tool requires: `tools.yaml` entry + role/team grants + persona-matrix rows.
- A new source requires: `config/sources/<id>.yaml` with `access` + `classification`.
- A team add-on (skills, instructions, context) goes in `config/teams/<team>.yaml` + `skills/teams/<team>/`.
- Every config file has `apiVersion: sdlc/v1` and `kind:`; unknown keys/references must fail validation.
- Run `uv run sdlc-config validate --env local` after any config change; review `sdlc-config diff`.

## Runtime config
See "Runtime Config Exposure" in docs/IMPLEMENTATION_PLAN.md.
- Only MCP servers (full bundle) and ingest (`Source.spec`) read config. Agents and prompts never read
  `config/`; they get per-user views through MCP tools (tools/list, list_skills, get_agent_context, whoami).
- Read config only through `ConfigStore.current()`. Take one snapshot per request; never cache policy across versions.
- `sdlc-config compile --env <env>` produces an immutable bundle (version = git SHA + content hash).
  Bundles never contain secrets; `${VAR}` values are resolved from env at load time.
- Startup fails closed without a valid bundle; reload keeps the last-known-good. Rollback = move the `current` pointer.
- Viewing another user's policy (`config_explain`) is an admin-only tool; `whoami(explain)` shows only the caller's own view.

## Security rules
- Authorization lives in the MCP server, never in prompts or agent code.
- Entra is the only trusted issuer. Tokens must be v2 (iss `https://login.microsoftonline.com/<tid>/v2.0`),
  `aud` = the sdlc-mcp client ID (v2) or `api://<client id>`, `scp` contains `access_as_user` (user tokens only),
  `tid` = our tenant, plus signature (JWKS) and exp. Implemented in `sdlc_auth.entra.EntraTokenVerifier`.
- The MCP server refuses to start without valid config and `ENTRA_TENANT_ID` / `ENTRA_API_CLIENT_ID` (fail closed).
- Users whose token omits groups (overage) get no groups unless the Graph fallback secret is set.
- Deny-by-default. Filter tools/list AND re-check on every tools/call.
- All DB reads go through `sdlc_db` with `app.allowed_sources` + `app.max_classification` set (Postgres RLS).
- Agents forward the user's bearer token via `get_user_token(context)`; never use a service token for user calls.
- Downstream systems use service credentials only after the RBAC check passes.
- Audit every tool call: oid, teams, roles, tool, args hash, decision, matched rule, config_version.
- Secrets only in `.env` (local) / Secret Manager (GCP). Never commit them.

## Commands
- `uv sync --all-packages`   install every workspace member (plain `uv sync` installs only the root)
- `docker compose up -d --build --wait`   postgres (127.0.0.1:5432), mcp-bootstrap (:8080), agent-bootstrap / adk web (:8000)
- DB connections use standard `PG*` env vars; the app role `sdlc_app` is non-superuser (RLS applies). Init: `db/bootstrap/README.md`.
- `uv run adk web agents`    run the dev UI outside Docker (needs `SDLC_MCP_URL`)
- `uv run pytest`            unit tests; e2e tests skip without the stack + Gemini creds
- `uv run --env-file .env pytest tests/e2e`   exit-gate tests (agent e2e, DB + pgvector)
- `uv run python scripts/mcp_whoami.py --token <entra token>`   manual identity check (see docs/ENTRA_SETUP.md)
- `.\scripts\entra_setup.ps1 -TestUserA <upn> -TestUserB <upn> [-DryRun] [-WriteLocalFiles]`   idempotent Entra provisioning
  (Windows: `az` is az.cmd, so never pass inline JSON or parentheses as az args; use `--body @file`)
- Tests never read the real `config/env/local/groups.yaml`; the `config_dir` fixture swaps in a fixed test GroupMap
- `uv run ruff check . && uv run ruff format .`
- `uv run --env-file .env sdlc-config validate --env local` (`--dummy-env` for a structure-only check without Entra values); `explain`/`diff` arrive in Stage 3

## Workspace conventions
- uv workspace members are listed explicitly in the root `pyproject.toml`; add each new component there.
- Agent packages under `agents/` are virtual uv projects (`package = false`); `adk web agents` imports them by folder name.
- Dockerfiles build from the repo root: `docker build -f <component>/Dockerfile .`.
- ADK 2 needs the `google-adk[mcp]` extra for `McpToolset`.
- Gemini runs on Vertex AI via gcloud ADC (project `cloud-migration-agent`, location `global`, model `gemini-3.8-flash`). ADC has no quota project, so `.env` sets `GOOGLE_CLOUD_QUOTA_PROJECT`. The agent container gets only the ADC file, mounted at `/secrets/adc.json`.
- Python 3.12 (`.python-version`); ruff formats code only, not markdown snippets.
- Only MCP servers and ingest get DB credentials. Agent containers get an explicit env allow-list, never the whole `.env`.
- Tests: `--import-mode=importlib` + `pythonpath=["."]`; shared helpers live in `tests/support/` (e.g. `FakeEntra` mints
  Entra-shaped RS256 tokens), fixtures in `tests/conftest.py`. MCP server tests run a real uvicorn server in a thread.
- New config kinds: add a JSON Schema in `config/schemas/` and register the kind in `sdlc_config/loader.py` (`_KINDS`).
