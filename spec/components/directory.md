---
type: Component
title: Directory
description: Knows the platform's users and teams, who belongs to which team, and in what team role.
tags: [component, control]
status: draft
x-layer: control
x-folder: libs/sdlc_directory/
x-depends-on: [/components/configuration-registry]
x-satisfies: [/requirements/functional/FR-IDN-001, /requirements/functional/FR-TEAM-001, /requirements/functional/FR-TEAM-002, /requirements/functional/FR-TEAM-004, /requirements/functional/FR-AUTHZ-007, /requirements/functional/FR-WFL-007, /requirements/functional/FR-HUM-002, /requirements/non-functional/NFR-HOST-001]
---

# Purpose

Workflows run for a user or for a team. The Directory is the single answer to "which teams is this
user in, and as what?"

# Responsibilities

- Resolve a user's team memberships, team roles and user groups from the users declared in configuration ([DEC-0010](../decisions/DEC-0010.md)); Cloud Identity groups are not read for now.
- Hold team profiles: owners, systems the team owns, default knowledge sources, team workflow settings.
- Serve membership to the [Access Policy](access-policy.md), [Human Tasks](human-tasks.md) routing and the UI.

# Out of scope

- Granting permissions: roles and their grants are policy.
- Changing membership at run time: it is a configuration change, published and activated like any other.

# Interfaces

- Provides: `memberships(user)`, `members(team)`, `team(team_id)`.
- Consumes: team, user-group and user declarations from the [Configuration Registry](configuration-registry.md).

# Depends on

- [Configuration Registry](configuration-registry.md)

# Owns

- Nothing; teams, team profiles and memberships are declared in configuration.

# Requirements

- [FR-IDN-001: Sign-in with Cloud Identity, federated from Entra ID](../requirements/functional/FR-IDN-001.md)
- [FR-TEAM-001: Teams declared in configuration](../requirements/functional/FR-TEAM-001.md)
- [FR-TEAM-002: Team context](../requirements/functional/FR-TEAM-002.md)
- [FR-TEAM-004: Many teams per user](../requirements/functional/FR-TEAM-004.md)
- [FR-AUTHZ-007: Grants to teams and user groups](../requirements/functional/FR-AUTHZ-007.md)
- [FR-WFL-007: Team parameter overrides](../requirements/functional/FR-WFL-007.md)
- [FR-HUM-002: Task routing](../requirements/functional/FR-HUM-002.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)

# Realisation

- Library `libs/sdlc_directory`, used by user_agent_mcp; no directory service is called
  ([DEC-0010](../decisions/DEC-0010.md)).
- Teams, their roles and user groups are declared in `config/`. Each environment lists its users by email in
  `config/env/<env>/users.yaml`, which is not committed: a team alone gives its `member` role, `team:role`
  another declared role, and `user_groups` the user groups. The compiler refuses a team, role or user group
  that is not declared; a user not listed is in no team.
- The platform has no screen or tool to change membership.
