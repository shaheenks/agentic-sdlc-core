---
type: Component
title: sdlc_config
description: Config loading and validation, the resolver that produces each caller's effective policy, bundles and the sdlc-config CLI.
area: Libraries
tags:
- component
- libraries
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../libs/sdlc_config
satisfies:
- /requirements/functional/FR-AUTHZ-001
- /requirements/functional/FR-AUTHZ-002
- /requirements/functional/FR-AUTHZ-003
- /requirements/functional/FR-AUTHZ-004
- /requirements/functional/FR-AUTHZ-005
- /requirements/functional/FR-AUTHZ-006
- /requirements/functional/FR-CFG-001
- /requirements/functional/FR-CFG-002
- /requirements/functional/FR-CFG-003
- /requirements/functional/FR-IDN-002
- /requirements/functional/FR-IDN-003
- /requirements/functional/FR-SKILL-001
- /requirements/functional/FR-SKILL-002
- /requirements/functional/FR-TEAM-001
- /requirements/non-functional/NFR-MAINT-004
- /requirements/non-functional/NFR-PORT-001
- /requirements/non-functional/NFR-REL-001
- /requirements/non-functional/NFR-SEC-001
- /requirements/non-functional/NFR-SEC-002
- /requirements/non-functional/NFR-SEC-004
- /requirements/non-functional/NFR-SEC-007
- /requirements/non-functional/NFR-SEC-008
verified_by:
- tests/config
- tests/policy/test_app_roles.py
sources:
- id: readme
  resource: ../../libs/sdlc_config/README.md
  title: libs/sdlc_config/README.md
---

# Purpose

Loads `config/`, validates it against JSON Schemas and cross-references, and resolves a principal's identities into an `EffectivePolicy`. Delivers configuration to services through `ConfigStore`.

Code: `libs/sdlc_config`

# Responsibilities

- Loader and schemas for every config kind; unknown keys and references fail.
- Resolver: identities to teams, roles, tools, skills, sources, argument limits and rate limits.
- Document-flow defaults and skill package validation.
- Bundles: compile, activate, verify; `ConfigStore` with reload and last-known-good.
- CLI: `validate`, `explain`, `diff`, `compile`, `activate`, `users sync`.
- Host allowlist for remote sources.

# Depends on

- [sdlc_secrets](sdlc_secrets.md)

# Requirements

- [FR-AUTHZ-001: Selective disclosure of tools](../requirements/functional/FR-AUTHZ-001.md) - Resolves the tools a caller may see.
- [FR-AUTHZ-002: Per-call authorization with argument limits](../requirements/functional/FR-AUTHZ-002.md) - Unions argument limits across teams.
- [FR-AUTHZ-003: Role hierarchy with classification ceilings](../requirements/functional/FR-AUTHZ-003.md) - Resolves role inheritance and classification ceilings.
- [FR-AUTHZ-004: Per-user rate limits](../requirements/functional/FR-AUTHZ-004.md) - Resolves rate limits from the platform baseline and team limits.
- [FR-AUTHZ-005: Data access granted per source](../requirements/functional/FR-AUTHZ-005.md) - Resolves readable sources from `Source.access`.
- [FR-AUTHZ-006: Team roles are scoped to their team](../requirements/functional/FR-AUTHZ-006.md) - Holds roles per scope (platform or team), checks team skills and source roles in their own team, computes the ceiling per source, and rejects a role used as both a platform and a team role.
- [FR-CFG-001: Access declared in configuration](../requirements/functional/FR-CFG-001.md) - Validates all configuration.
- [FR-CFG-002: Explain and diff effective permissions](../requirements/functional/FR-CFG-002.md) - `explain` and `diff` commands.
- [FR-CFG-003: Immutable config bundles with rollback](../requirements/functional/FR-CFG-003.md) - Bundles and `ConfigStore`.
- [FR-IDN-002: Membership from groups, app roles and direct members](../requirements/functional/FR-IDN-002.md) - Maps groups, app roles and direct members to teams and roles.
- [FR-IDN-003: Users can see their own access](../requirements/functional/FR-IDN-003.md) - Produces the explanation of a policy.
- [FR-SKILL-001: Skills served per user](../requirements/functional/FR-SKILL-001.md) - Resolves the skills a caller may see.
- [FR-SKILL-002: Skill naming and layout](../requirements/functional/FR-SKILL-002.md) - Validates skill names and layout.
- [FR-TEAM-001: Team customization of behaviour](../requirements/functional/FR-TEAM-001.md) - Validates team add-ons and merges document-flow defaults.
- [NFR-MAINT-004: Permission changes are reviewable](../requirements/non-functional/NFR-MAINT-004.md) - Provides the per-persona diff.
- [NFR-PORT-001: Tenant-agnostic identity](../requirements/non-functional/NFR-PORT-001.md) - Identity hosts come from `platform.yaml`.
- [NFR-REL-001: Safe configuration reload](../requirements/non-functional/NFR-REL-001.md) - Atomic reload with last-known-good; one snapshot per version.
- [NFR-SEC-001: Single enforcement point](../requirements/non-functional/NFR-SEC-001.md) - Is the only way services read configuration.
- [NFR-SEC-002: Deny by default](../requirements/non-functional/NFR-SEC-002.md) - Deny wins in resolution.
- [NFR-SEC-004: Fail closed](../requirements/non-functional/NFR-SEC-004.md) - Startup fails closed on invalid configuration.
- [NFR-SEC-007: Secrets handling](../requirements/non-functional/NFR-SEC-007.md) - Keeps secrets as references; bundles contain none.
- [NFR-SEC-008: Controlled egress](../requirements/non-functional/NFR-SEC-008.md) - Defines the host allowlist.

# Verification

- `tests/config`
- `tests/policy/test_app_roles.py`
