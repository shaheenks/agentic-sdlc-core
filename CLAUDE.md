# Agentic SDLC

ADK-based SDLC agents composed from skills. Central MCP server(s) serve skills, tools and
knowledge, and enforce Entra ID identity + app-role-based RBAC defined in `config/`. Postgres +
pgvector stores embeddings and the knowledge graph. Local: docker compose. Prod: GCP.

Architecture overview: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Built features and their status:
[docs/FEATURE_INVENTORY.md](docs/FEATURE_INVENTORY.md) (update it with the plan after each milestone). Current plan: [docs/plans/version-03.md](docs/plans/version-03.md) (started 2026-11-05; first milestone P5 artifacts; staging + enterprise identity, A2UI/A2A, agent runtimes, write tools, more connectors proposed); history: [docs/plans/archive/version-02.md](docs/plans/archive/version-02.md) (closed 2026-11-06), [docs/plans/archive/version-01.md](docs/plans/archive/version-01.md) (new sources, AG-UI web app with CopilotKit, per-user PAT connections, GCP dev) and [docs/plans/archive/version-00.md](docs/plans/archive/version-00.md). Check which stage is
current before adding features, and don't build ahead of the current stage's exit gate.

## Where things are
- `agents/`, `mcp_servers/`, `ingest/`, `libs/`, `ui/copilotkit`: the code. One concept per component, with what it does and
  the requirements it satisfies: [knowledge/components](knowledge/components/index.md).
- `skills/` SKILL.md content, `config/` the access model, `db/` schema + RLS, `infra/` Terraform (GCP), `tests/`.
- `knowledge/` the specification (OKF 0.2 bundle): requirements, components, traceability, rule sets, change records.
- `docs/` design docs, plans (`docs/plans/`) and how-to guides (`docs/guides/`); map: [docs/README.md](docs/README.md).

Each area has a starter component (`agents/user_agent`, `mcp_servers/core_mcp`, `ingest/bootstrap`, `db/bootstrap`).
Add new components as siblings instead of growing a starter indefinitely. Shared code goes in `libs/`, never copied between components.

## Knowledge bundle and changes
`knowledge/` is the specification: requirements (`FR-*`, `NFR-*`), one concept per component with the requirements it
satisfies, and the generated traceability matrix. Conventions: [knowledge/conventions.md](knowledge/conventions.md).
- Before changing a component, read `knowledge/components/<name>.md` and the requirements it links.
- Every feature, behaviour change, fix or refactor starts as a change record `knowledge/changes/CH-<nnnn>.md` naming
  the requirement IDs it adds, modifies or retires and the components it touches. A fix or refactor has no requirement
  delta. Start code work only once the user has approved the record (`status: stable` + `verified` by `human:`).
- Never mark a concept `stable` or add a `human:` verification yourself; that is the user's review. Editing a reviewed
  requirement in substance sets it back to `status: draft`.
- In the same PR as the code: update the requirement and component concepts (`satisfies`, `verified_by`), set the
  record to `state: done`, add a line to `knowledge/log.md`. Use requirement IDs in commits and PR descriptions.
- A new workspace member needs a component concept; a `live`/`built`/`stub` requirement needs a component.
- `uv run python scripts/okf_bundle.py build` (indexes + matrix), then `... lint`; CI job `knowledge` runs the lint.
- Work that predates the bundle (2026-11-10) is not backfilled into change records.

## Always
These hold for every change. The full rules, with their reasons and exceptions, are in the rule sets below.
- **Access is declared, not coded.** All access lives in `config/`; never hardcode roles, app roles, tool lists or data scopes.
  Authorization lives in the MCP server, never in prompts or agent code. Deny by default; when identity or config cannot
  be verified, fail closed.
- **Calls are made as the user.** Agents forward the user's bearer token; never use a service token for user calls. All DB
  reads go through `sdlc_db` under row-level security.
- **Nothing sensitive leaves its place.** Never commit secrets, tenant IDs, app IDs, group IDs or test-user UPNs
  (`config/env/*/users.yaml` and `blocked.yaml` are git-ignored). Never log raw tokens or argument values.
- **Cloud and tenant actions belong to the user.** Do not create or change GCP resources unless asked, and do not run
  `terraform` or `gcp_deploy.ps1` yourself. Any Entra change needs the user's confirmation for that action; check
  `az account show` first and say which account read-only queries run as.
- **Current phase: development.** It must work on both `localhost` and the Cloudflare Tunnel; hostnames and URLs are
  configuration, never hard-coded.
- **Check your work.** After a config change: `uv run sdlc-config validate --env local` and review `sdlc-config diff`.
  Before finishing: `uv run ruff check . && uv run ruff format .` and `uv run pytest`.

## Read before you work
The rule sets are binding, not background. Read the ones for your area before changing anything there.

| Working on | Read first |
|---|---|
| `config/`: roles, tools, skills, teams, sources, app roles, naming | [knowledge/rules/configuration.md](knowledge/rules/configuration.md) |
| How services load config: `ConfigStore`, bundles, activation | [knowledge/rules/runtime-config.md](knowledge/rules/runtime-config.md) |
| Auth, tokens, the MCP server, audit, connections, artifacts, secrets | [knowledge/rules/security.md](knowledge/rules/security.md) |
| Environments, hostnames, the tunnel, GCP | [knowledge/rules/environments.md](knowledge/rules/environments.md) |
| The Entra tenant, test users, enterprise tenants | [knowledge/rules/tenants.md](knowledge/rules/tenants.md) |
| Running, testing, ingest, tracing, CLI tools, CI, deployment | [knowledge/rules/commands.md](knowledge/rules/commands.md) |
| Repo layout, the uv workspace, ADK and MCP sessions, tests, data tables, the graph | [knowledge/rules/workspace.md](knowledge/rules/workspace.md) |
| A specific component | `knowledge/components/<name>.md` and the requirements it links |
| Setting up or operating something by hand | [docs/guides](docs/README.md#guides) |
