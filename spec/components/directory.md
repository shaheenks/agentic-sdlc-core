---
type: Component
title: Directory
description: Knows the platform's users and teams, who belongs to which team, and in what team role.
tags: [component, control]
status: draft
x-layer: control
x-depends-on: [/components/configuration-registry]
x-satisfies: [/requirements/functional/FR-IDN-001, /requirements/functional/FR-TEAM-001, /requirements/functional/FR-TEAM-002, /requirements/functional/FR-TEAM-004, /requirements/functional/FR-AUTHZ-007, /requirements/functional/FR-WFL-007, /requirements/functional/FR-HUM-002, /requirements/non-functional/NFR-HOST-001]
---

# Purpose

Workflows run for a user or for a team. The Directory is the single answer to "which teams is this
user in, and as what?"

# Responsibilities

- Resolve a user's team memberships and team roles from Cloud Identity groups (provisioned from Entra ID), including nested groups, and the team mappings declared in configuration.
- Hold team profiles: owners, systems the team owns, default knowledge sources, team workflow settings.
- Serve membership to the [Access Policy](access-policy.md), [Human Tasks](human-tasks.md) routing and the UI.

# Out of scope

- Granting permissions: roles and their grants are policy.
- Creating or changing groups: they are managed in Entra ID and provisioned to Cloud Identity.

# Interfaces

- Provides: `memberships(user)`, `members(team)`, `team(team_id)`.
- Consumes: team declarations from the [Configuration Registry](configuration-registry.md); group memberships from the Cloud Identity Groups API.

# Depends on

- [Configuration Registry](configuration-registry.md)

# Owns

- A resolved-membership cache. Team profiles are declared in configuration.

# Requirements

- [FR-IDN-001: Sign-in with Cloud Identity, federated from Entra ID](../requirements/functional/FR-IDN-001.md)
- [FR-TEAM-001: Teams from Cloud Identity groups](../requirements/functional/FR-TEAM-001.md)
- [FR-TEAM-002: Team context](../requirements/functional/FR-TEAM-002.md)
- [FR-TEAM-004: Many teams per user](../requirements/functional/FR-TEAM-004.md)
- [FR-AUTHZ-007: Grants to teams and user groups](../requirements/functional/FR-AUTHZ-007.md)
- [FR-WFL-007: Team parameter overrides](../requirements/functional/FR-WFL-007.md)
- [FR-HUM-002: Task routing](../requirements/functional/FR-HUM-002.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)

# Realisation

- Cloud Identity Groups API, read by the component's service account with group-reader access; results cached per user for a short time.
- A shared library under `libs/`, self-contained, used by user_agent_mcp, Knowledge Search and the sdlc_ui BFF.
- Teams and their membership are declared only in configuration (the groups that give membership and team roles); the platform has no screen or tool to change membership.
