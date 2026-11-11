---
type: Component
title: config
description: 'Declarative YAML for the access model: platform, roles, tools, skills, teams, sources, connections and per-environment identity maps.'
area: Content and configuration
tags:
- component
- content-and-configuration
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../config
satisfies:
- /requirements/functional/FR-AUTHZ-002
- /requirements/functional/FR-AUTHZ-003
- /requirements/functional/FR-AUTHZ-004
- /requirements/functional/FR-AUTHZ-005
- /requirements/functional/FR-AUTHZ-006
- /requirements/functional/FR-CFG-001
- /requirements/functional/FR-CONN-001
- /requirements/functional/FR-CONN-003
- /requirements/functional/FR-IDN-002
- /requirements/functional/FR-IDN-004
- /requirements/functional/FR-KNOW-001
- /requirements/functional/FR-KNOW-006
- /requirements/functional/FR-SKILL-001
- /requirements/functional/FR-TEAM-001
- /requirements/non-functional/NFR-PRIV-003
- /requirements/non-functional/NFR-SEC-008
verified_by:
- tests/config/test_repo_teams.py
- tests/config/test_rbac_config.py
- tests/config/test_sources_config.py
- tests/policy/matrix.yaml
sources:
- id: readme
  resource: ../../config/README.md
  title: config/README.md
---

# Purpose

The single place access is declared. Validated by JSON Schemas in `config/schemas/`; tenant-specific files under `config/env/` are git-ignored.

Code: `config`

# Responsibilities

- `platform.yaml`, `roles.yaml`, `tools.yaml`, `skills.yaml`, `connections.yaml`.
- `teams/`, `sources/`, `schemas/`.
- `env/<env>/`: group map, direct members and block list (examples only in git).

# Depends on

No other component.

# Requirements

- [FR-AUTHZ-002: Per-call authorization with argument limits](../requirements/functional/FR-AUTHZ-002.md) - Tool catalog declares the arguments teams may limit.
- [FR-AUTHZ-003: Role hierarchy with classification ceilings](../requirements/functional/FR-AUTHZ-003.md) - Role set.
- [FR-AUTHZ-004: Per-user rate limits](../requirements/functional/FR-AUTHZ-004.md) - Platform baseline and team rate limits.
- [FR-AUTHZ-005: Data access granted per source](../requirements/functional/FR-AUTHZ-005.md) - Source access rules and classifications.
- [FR-AUTHZ-006: Team roles are scoped to their team](../requirements/functional/FR-AUTHZ-006.md) - Team roles `member` and `approver` are granted only by team membership; platform roles only by global bindings.
- [FR-CFG-001: Access declared in configuration](../requirements/functional/FR-CFG-001.md) - Is the declared access model.
- [FR-CONN-001: Users connect their own accounts](../requirements/functional/FR-CONN-001.md) - Connection catalog.
- [FR-CONN-003: Atlassian and Data Center connections](../requirements/functional/FR-CONN-003.md) - The `atlassian` connection and Data Center editions.
- [FR-IDN-002: Membership from groups, app roles and direct members](../requirements/functional/FR-IDN-002.md) - Group map and direct-member list per environment.
- [FR-IDN-004: Revocation of access](../requirements/functional/FR-IDN-004.md) - Block list per environment.
- [FR-KNOW-001: Ingest declared sources](../requirements/functional/FR-KNOW-001.md) - Source definitions.
- [FR-KNOW-006: Atlassian and Bitbucket sources](../requirements/functional/FR-KNOW-006.md) - Confluence, Jira and Bitbucket source types.
- [FR-SKILL-001: Skills served per user](../requirements/functional/FR-SKILL-001.md) - Skill catalog and grants.
- [FR-TEAM-001: Team customization of behaviour](../requirements/functional/FR-TEAM-001.md) - Team add-ons and flow defaults.
- [NFR-PRIV-003: Tenant data stays out of the repository](../requirements/non-functional/NFR-PRIV-003.md) - Tenant files are git-ignored; only examples are committed.
- [NFR-SEC-008: Controlled egress](../requirements/non-functional/NFR-SEC-008.md) - Platform host allowlist.

# Verification

- `tests/config/test_repo_teams.py`
- `tests/config/test_rbac_config.py`
- `tests/config/test_sources_config.py`
- `tests/policy/matrix.yaml`
