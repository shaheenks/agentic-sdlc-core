# sdlc_config

Config loading, validation, resolution and runtime delivery. Stages 2-7.

**Implemented (Stage 2):** kinds `Platform` + `GroupMap` (schemas in config/schemas/), `${VAR}`
substitution (unset => error), `load_snapshot`, `ConfigStore` (local folder, file watch,
fail-closed start, last-known-good reload, subscribers), CLI `validate [--dummy-env]`.

**Implemented (Stage 3):** kinds `RoleSet`, `ToolCatalog`, `Team` (multi-file) with cross-reference
checks; `resolve()` -> `EffectivePolicy` (source rules for every grant, deny and limit) and
`PolicyCache`; personas; CLI `explain` and `diff`.

**Implemented (Stages 4-6):** `SkillCatalog` + team add-ons, `Source` (data access, graph settings),
`readable_sources` (current classification in the RLS context).

**Implemented (H4, local part of Stage 7b):** config bundles (`bundles.py`): `sdlc-config compile`,
`activate`, `bundles`; `ConfigStore.from_bundles()` (and `SDLC_CONFIG_BUNDLES` in `from_env`).
GCS + Pub/Sub delivery is still planned (Stage 7b on GCP).
Design: docs/IMPLEMENTATION_PLAN.md → "Configuration Model" and "Runtime Config Exposure".

## Components
- **Schemas** - JSON Schema per kind (config/schemas/), strict: unknown keys/refs fail.
- **compile** - `sdlc-config compile --env <env> --out <root> [--activate]`: validate, then copy
  exactly the files the loader read (config, schemas, env overlay incl. `groups.yaml`, SKILL.md,
  team addenda) into `<root>/<version>/tree/` with `manifest.json` (sha256 per file). Version =
  `<git sha>-<content hash>`: immutable; recompiling unchanged content is a no-op. Files stay raw,
  so `${VAR}` placeholders are unresolved: no secrets. Bundles do contain tenant group IDs, so bundle
  roots stay out of git (`.bundles/` is ignored).
- **activate / bundles** - `sdlc-config activate <version> --root <root> [--env <env>]` moves the
  `current` pointer (atomic replace, only to a fully verified bundle); rollback = activate an older
  version. `sdlc-config bundles --root <root>` lists them (`*` = active).
- **ConfigStore** - `ConfigStore.from_env()`: `SDLC_CONFIG_BUNDLES` (bundle root) if set, else the local
  folder `SDLC_CONFIG_DIR` (dev, file watch). Bundles are verified on every load (every file against
  the manifest, no extra files, recomputed version = bundle version, env matches). Fail-closed
  startup, last-known-good on a bad reload; a pointer move triggers the reload. GCS: Stage 7b.
  - `store.current()` → immutable `Snapshot` (one per request)
  - `snap.resolve(principal)` → `EffectivePolicy` (cached per oid + groups hash + version)
  - `snap.version`, `store.subscribe(on_change)`
- **Resolver** - groups → teams → roles → tools/skills/sources/agent context; deny wins.

## Exposure
- CLI: `validate`, `compile`, `activate`, `bundles`, `explain --persona|--groups`, `diff`
- MCP tools (served by MCP servers, RBAC-gated): `whoami(explain=true)` (own view),
  `config_explain(upn)` and `config_info()` (admin only)
- HTTP: `/healthz`, `/readyz` report `config_version`
