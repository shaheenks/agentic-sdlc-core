# libs

Shared Python packages reused by all components. Never copy this code into components.

| Package | Purpose |
|---|---|
| `sdlc_auth` | Entra token validation, group overage fallback, user-token passthrough for agents |
| `sdlc_config` | Config loader, JSON Schemas, resolver (`EffectivePolicy`), CLI; host allowlist helpers |
| `sdlc_policy` | Tool authorization decisions, rate limits |
| `sdlc_db` | Postgres/pgvector access under RLS, migrations, knowledge and graph queries |
| `sdlc_web` | Agent web app behind oauth2-proxy (token re-validation, user binding) |
| `sdlc_agent` | Agent helpers (team context) |
| `sdlc_secrets` | Secret references resolved at runtime: `env` or Google Secret Manager, short cache (version-01 M0) |
