---
type: Rule Set
title: Commands
description: "Every command for running, testing, ingesting, tracing, configuring and deploying, with the rules attached to each."
tags: [rules]
status: draft
---

Binding working rules for contributors and coding agents, moved word for word from `CLAUDE.md` on 2026-11-10.
Paths are relative to the repository root.

# Commands

- `uv sync --all-packages`   install every workspace member (plain `uv sync` installs only the root)
- `docker compose up -d --build --wait`   postgres (:5432), core-mcp (:8080), user-agent (internal :8000), oauth2-proxy (:4180)
- `docker compose --profile tunnel up -d --wait`   also starts `oauth2-proxy-public` on 127.0.0.1:4181. Public endpoints
  `https://app-sdlc-dev.shaheenks.co.in` (UI -> localhost:4181) and `https://mcp-sdlc-dev.shaheenks.co.in/mcp` (-> localhost:8080) go
  through the host's `Cloudflared` Windows service (tunnel + hostnames managed in the Cloudflare dashboard). Run exactly one
  connector per tunnel. See docs/guides/CLOUDFLARE_TUNNEL.md.
  Public names are one level deep (`*-sdlc-dev.shaheenks.co.in`) so free Universal SSL covers them.
- Open **http://localhost:4180** and sign in with Entra to use the agents (`/` opens the CopilotKit chat at /chat/; dev UI at /dev-ui/; the navbar reads `GET /me` and `GET /connections/`). The agent
  and chat app ports are not published. AG-UI rules: the chat app forwards ONLY `X-Forwarded-Access-Token` to `/agui`
  (`forwardHeaders.allow`), stores no conversations (`PassThroughAgentRunner`, never `InMemoryAgentRunner`), has no frontend
  tools that read data; `/agui` binds the user id to the token `oid` and strips client `temp:`/`app:`/`user:` state.
  Chat history (version-02 N15): `GET /threads` (agent, caller's sessions only) feeds the sidebar; opening a thread replays
  it in `PassThroughAgentRunner.connect` from the agent's `/agents/state` as the same user; runs send only the latest turn.
  `DELETE /threads/{id}` deletes the caller's own chat (needs `X-SDLC-Request: 1`; others' and missing threads answer 404).
  ADK developer tools (builder, deploy, evals, tests, other users' traces) are off; `SDLC_DEV_TOOLS=true` enables them (never outside local dev).
- DB connections use standard `PG*` env vars. Roles: `sdlc_owner` (migrations), `sdlc_app` (MCP, read-only except its own rows in `artifacts`), `sdlc_ingest`
  (writes); none bypasses RLS. Init: `db/bootstrap/README.md`. On the host use `PGHOST=127.0.0.1` (`localhost` tries IPv6
  first and hangs; Docker publishes Postgres on IPv4 only).
- `uv run --env-file .env sdlc-agent-web`   agent web app outside Docker (expects a token in `X-Forwarded-Access-Token` or `Authorization: Bearer`)
- `uv run pytest`            unit tests; e2e tests skip without the stack + Gemini creds
- `docker compose run --rm migrate`   apply `db/migrations` as `sdlc_owner` (host: `uv run --env-file .env sdlc-db migrate`)
- `docker compose run --rm ingest run --all | --source <id> [--dry-run] [--force]`   ingest `config/sources` as `sdlc_ingest`
  (profile `ingest`, never started by `up`; host: `uv run --env-file .env sdlc-ingest run --all`)
- `uv run --env-file .env pytest tests/db`   RLS/ingest/search/graph tests on a throwaway `sdlc_test` database (needs the postgres container)
- `SDLC_EVAL=1 uv run --env-file .env pytest tests/evals -s`   retrieval eval (vector vs hybrid) on the ingested dev DB, live Vertex
- `uv run --env-file .env pytest tests/e2e`   exit-gate tests (DB + pgvector; the Stage 2 agent e2e needs `SDLC_E2E_USER_TOKEN`, see docs/guides/ENTRA_SETUP.md)
- `uv run python scripts/mcp_whoami.py --token <entra token>`   manual identity check (see docs/guides/ENTRA_SETUP.md)
- `uv run python scripts/a2a_client.py [--url <app>] [--context <id>] "question"`   A2A check (version-03 P4; token in `SDLC_TOKEN`);
  `/a2a` (JSON-RPC, A2A 0.3) + public `/.well-known/agent-card.json` on the agent (`SDLC_A2A_AGENT`), bearer tokens through oauth2-proxy
- `.\scripts\entra_setup.ps1 -TestUserA <upn> -TestUserB <upn> [-DryRun] [-WriteLocalFiles]`   idempotent Entra provisioning
  (Windows: `az` is az.cmd, so never pass inline JSON or parentheses as az args; use `--body @file`)
- Tests never read the real `config/env/local/users.yaml`; the `config_dir` fixture swaps in fixed test users
- `uv run ruff check . && uv run ruff format .`
- Tracing: set `OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318` in `.env`, then `docker compose --profile observability up -d`;
  Jaeger UI http://localhost:16686. One agent turn is one trace across agent, MCP server and Postgres (context travels in
  MCP `_meta`, not HTTP headers; never add a per-call trace header: it would break one MCP session per conversation).
  Spans carry no prompts, responses, tokens or argument values (agent tool args export as `{}`). Audit records carry `trace_id`.
  GCP (version-02 N4): `cloud_trace = true` sets `SDLC_TRACE_TO_CLOUD=true` (Cloud Trace exporter, takes precedence over OTLP;
  `roles/cloudtrace.agent` on the MCP and app service accounts). Audit log queries: docs/guides/GCP_DEPLOYMENT.md "Audit views".
- `cd ui/copilotkit; npm ci; npm test; npm run typecheck; npm run build`   chat app checks (exact versions pinned; telemetry off)
- CI: `.github/workflows/ci.yml` (lint, config validate + PR permission diff, UI typecheck/test/build, tests on a pgvector service after
  `sdlc-db bootstrap` + `migrate`, terraform fmt/validate). No secrets or cloud calls in CI; tests must pass without `.env`
  (placeholder Entra IDs, HashEmbedder, FakeEntra).
- `uv run --env-file .env sdlc-config validate --env local` (`--dummy-env` for a structure-only check without Entra values;
  `--check-secrets` also resolves every secret reference and prints names + outcomes only; not in CI)
- `.\scripts\gcp_deploy.ps1 -EnvName dev -Step state|base|config|images|plan|apply|db|ingest|urls`   GCP deployment, run by the user (see
  docs/guides/GCP_DEPLOYMENT.md). PowerShell, not bash (Windows). Commit first: images and plan use the commit SHA as tag.
  `base`/`apply` create billable resources: only with the user's go-ahead. The saved plan contains secrets (git-ignored,
  deleted by `apply`).
- `uv run --env-file .env sdlc-db bootstrap`   extension, roles, schema, grants (idempotent; no true superuser needed, as on
  Cloud SQL); fails if any role can bypass RLS. The test database is built with it.
- `uv run sdlc-config explain --persona payments-member` | `--app-roles SDLC.User,SDLC.Payments.Member` | `--user <alias>` `[--json]` (`--dummy-env` works)
- `uv run sdlc-config diff [--from HEAD] [--to WORKTREE] [--exit-code]`   per-persona permission changes (review on every config PR)
- MCP tools: `whoami(explain=true)` (own view with source rules); `list_skills` / `load_skill` (per-user; hidden skills answer
  "unknown skill"; `list_skills` returns tags + team); `get_agent_context(team=)` (team instructions + context,
  your teams, default team, document flow defaults; a team you are not in = "unknown team"); `resolve_team(hints)`
  (viewer+, which of your teams); `search_knowledge` (viewer+, vector; + keyword matches on identifier terms when
  `platform.yaml` `knowledge.keyword_search`, version-03 P11, needs migration 007) and
  `graph_query` (viewer+, vector + knowledge graph), both under RLS; admin only: `config_info()`, `config_explain(app_roles, user)`
- Skills: a `"*"` skill grant (admin) covers every team's add-ons; team instructions are guidance, never authorization.
  `sdlc-config diff` cannot compare across the Stage 4 boundary (older revisions lack skills.yaml) or the Stage 6 boundary
  (older revisions enable a source graph without `platform.yaml` `knowledge.graph`); later revisions diff normally.
