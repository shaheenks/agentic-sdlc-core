# sdlc_config

Config loading, validation, resolution and runtime delivery. Stages 2-7.
Design: docs/IMPLEMENTATION_PLAN.md → "Configuration Model" and "Runtime Config Exposure".

## Components
- **Schemas** - JSON Schema per kind (config/schemas/), strict: unknown keys/refs fail.
- **compile** - `sdlc-config compile --env <env>`: validate, merge env overlay, expand inherits,
  index lookups, package referenced skill files → `bundle.json` + `manifest.json` (no secrets).
- **ConfigStore** - `ConfigStore.from_env()` loads from a local folder (file-watch) or GCS
  (`current` pointer + Pub/Sub reload). Fail-closed startup, last-known-good on bad reload.
  - `store.current()` → immutable `Snapshot` (one per request)
  - `snap.resolve(principal)` → `EffectivePolicy` (cached per oid + groups hash + version)
  - `snap.version`, `store.subscribe(on_change)`
- **Resolver** - groups → teams → roles → tools/skills/sources/agent context; deny wins.

## Exposure
- CLI: `validate`, `compile`, `explain --upn <upn> --env <env> [--version <v>]`, `diff`
- MCP tools (served by MCP servers, RBAC-gated): `whoami(explain=true)` (own view),
  `config_explain(upn)` and `config_info()` (admin only)
- HTTP: `/healthz`, `/readyz` report `config_version`
