---
type: Rule Set
title: Repo structure and workspace conventions
description: "Where each component lives, and conventions for the uv workspace, ADK and MCP sessions, tests, data tables and the knowledge graph."
tags: [rules]
status: draft
---

Binding working rules for contributors and coding agents, moved word for word from `CLAUDE.md` on 2026-11-10.
Paths are relative to the repository root.

# Repo structure

- `agents/<name>/`          ADK agents (`agents/user_agent` = starter root agent)
- `mcp_servers/<name>/`     FastMCP servers, streamable HTTP (`mcp_servers/core_mcp` = starter)
- `ingest/<component>/`     RAG + KG pipeline (`ingest/bootstrap` = pipeline + CLI; `ingest/loaders` = `sdlc_loaders`, one loader per source type)
- `libs/sdlc_auth`          Entra JWT validation, group overage fallback, `get_user_token(context)`
- `libs/sdlc_config`        Config loader + JSON Schemas + resolver → `EffectivePolicy`; CLI validate/explain/diff
- `libs/sdlc_policy`        Enforcement: tools/list filtering, call authz, arg constraints
- `libs/sdlc_db`            Postgres/pgvector access with RLS session context
- `libs/sdlc_connectors`    External systems: `HttpClient` (host allowlist), Atlassian converters, user connections (providers, per-user secret store, service)
- `libs/sdlc_artifacts`     Artifact content store (local folder / GCS) + limits (version-03 P5); metadata in `sdlc_db.artifacts`
- `libs/sdlc_secrets`       Secret references (`{env: X}` / `{secret: x}`) resolved at runtime: env or Secret Manager, 5-min cache
- `libs/sdlc_web`           Serves agents (ADK web app + AG-UI `/agui`) behind oauth2-proxy: token re-validation, user binding, token passthrough
- `ui/copilotkit`           CopilotKit chat app (Next.js) at `/chat/` behind oauth2-proxy; talks AG-UI to the agent's `/agui`
- `libs/sdlc_agent`         Agent helpers: `with_team_context` (per-session team instructions/context via `get_agent_context`, as the user)
- `skills/core/`, `skills/teams/<team>/`   SKILL.md content only (no access rules inside skills)
- `config/`                 platform, roles, tools, skills, `teams/`, `sources/`, `env/<env>/groups.yaml`, `schemas/`
- `db/bootstrap`, `db/migrations`   Schema + RLS
- `infra/`                  Terraform (GCP)
- `tests/`                  persona-matrix, resolver, RLS, e2e, retrieval evals
- `docs/`                   Design docs, plans (`docs/plans/`) and how-to guides (`docs/guides/`); map: docs/README.md
- `knowledge/`              OKF 0.2 knowledge bundle: requirements, component register, traceability, change records

Each area has a starter component (`agents/user_agent`, `mcp_servers/core_mcp`, `ingest/bootstrap`, `db/bootstrap`).
Add new components as siblings instead of growing a starter indefinitely. Shared code goes in `libs/`, never copied between components.

# Workspace conventions

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
  idle retention; GCP: Agent Engine sessions, `agentengine://` + full resource name, TTL from conversation start, `sdlc_web.sessions`). Options and trade-offs (Postgres, MCP session API, Agent Engine): ARCHITECTURE.md "Conversation storage".
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
