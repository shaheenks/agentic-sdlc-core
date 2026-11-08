# tests

`uv run pytest` (unit; DB tests skip without Postgres). Helpers in `support/` (e.g. `FakeEntra`), fixtures in `conftest.py`.

| Folder | Covers |
|---|---|
| `policy/` | Persona matrix (tools, skills, data rows), app roles, CODEOWNERS |
| `config/` | Loader, schemas, resolver, bundles, users.yaml, document flows, repo teams |
| `auth/` | Entra token validation, overage, proxy egress |
| `mcp/` | MCP server end to end (real uvicorn server): tools/list, authz, audit, rate limits, connections, teams |
| `db/` | RLS, ingest, vector / keyword / graph search, artifacts (throwaway `sdlc_test` database) |
| `ingest/`, `connectors/`, `secrets/`, `artifacts/` | Loaders and chunking, providers + HTTP allowlist, secret references, artifact store + limits |
| `agent/` | Team context, Goldfish reviewers, A2UI cards |
| `web/` | Agent web app: user binding, AG-UI, A2A, threads, sessions |
| `e2e/` | Exit-gate tests (need the stack; the agent e2e needs `SDLC_E2E_USER_TOKEN`) |
| `evals/` | Retrieval eval and team lens eval (`SDLC_EVAL=1`, live Vertex) |
