# libs

Shared Python packages reused by all components. Never copy this code into components.

| Package | Purpose |
|---|---|
| `sdlc_auth` | Entra token validation (user tokens, app roles), group overage handling (fail closed; Graph fallback off), user-token passthrough and MCP headers for agents |
| `sdlc_config` | Config loader, JSON Schemas, resolver (`EffectivePolicy`), document-flow defaults, bundles, CLI (`validate`, `explain`, `diff`, `compile`, `users sync`); host allowlist helpers |
| `sdlc_policy` | Tool authorization decisions, argument limits, rate limits |
| `sdlc_db` | Postgres/pgvector access under RLS, migrations, bootstrap; vector + keyword search, knowledge graph, artifact metadata |
| `sdlc_web` | Agent web app behind oauth2-proxy: token re-validation, user binding, AG-UI `/agui`, A2A `/a2a`, chat threads, session retention |
| `sdlc_agent` | Agent helpers: team context + `set_active_team`, Goldfish reviewers (`goldfish_review`), A2UI cards |
| `sdlc_connectors` | External systems: `HttpClient` (host allowlist), providers (Cloud / Data Center), Atlassian converters, per-user connection store, reconcile |
| `sdlc_secrets` | Secret references resolved at runtime: `env` or Google Secret Manager, short cache (version-01 M0) |
| `sdlc_artifacts` | Artifact content store (`file://` / `gs://`) and limits (version-03 P5) |

Feature status per library: [docs/FEATURE_INVENTORY.md](../docs/FEATURE_INVENTORY.md) §2.3.
