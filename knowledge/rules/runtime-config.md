---
type: Rule Set
title: Runtime config
description: "How services load configuration at runtime: ConfigStore, bundles, activation, rollback and the GCP config store."
tags: [rules]
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T22:53:19+05:30'
---

Binding working rules for contributors and coding agents, moved word for word from `CLAUDE.md` on 2026-11-10.
Paths are relative to the repository root.

# Runtime config

See "Runtime Config Exposure" in docs/plans/archive/version-00.md.
- Only MCP servers (full bundle) and ingest (`Source.spec`) read config. Agents and prompts never read
  `config/`; they get per-user views through MCP tools (tools/list, list_skills, get_agent_context, whoami).
- Read config only through `ConfigStore.current()`. Take one snapshot per request; never cache policy across versions.
- `sdlc-config compile --env <env> --out <root> [--activate]` produces an immutable bundle (version = git SHA +
  content hash); `sdlc-config activate <version> --root <root>` moves the `current` pointer; `SDLC_CONFIG_BUNDLES=<root>`
  makes services load bundles instead of the folder. Bundles never contain secrets (`${VAR}` stays unresolved until
  load) but do contain the tenant `groups.yaml`: keep bundle roots out of git (`.bundles/`). Dev uses the watched folder.
- Startup fails closed without a valid bundle; reload keeps the last-known-good. Rollback = move the `current` pointer.
- GCP (version-02 N13): with `config_store_bucket` set, the MCP service and ingest job read bundles from
  `gs://<bucket>/bundles/<env>/` (mounted read-only); the MCP server polls `current` (`SDLC_CONFIG_POLL_SECONDS`, 60).
  Publish: `gcp_deploy.ps1 -Step config` (compile, upload, move `current` last); rollback: `-ConfigVersion <v>`.
  `ConfigStore.start_updates()` picks polling (bundles) or file watching (folder). Bundles ignore `SDLC_USERS_FILE`.
  Ingest resolves relative source locations against `SDLC_SOURCES_ROOT` (default: config dir parent; bundles: repo root).
- Viewing another user's policy (`config_explain`) is an admin-only tool; `whoami(explain)` shows only the caller's own view.
