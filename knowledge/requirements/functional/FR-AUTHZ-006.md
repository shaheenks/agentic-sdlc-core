---
type: Functional Requirement
title: Team roles are scoped to their team
description: A team role grants access only to that team's resources, never to another team's.
area: Authorization
tags:
- requirement
- functional
- authorization
status: draft
priority: must
implementation: planned
sources:
- id: design
  resource: ../../../docs/designs/workflow-platform.md
  title: Workflow platform target design
- id: change
  resource: ../../changes/CH-0008.md
  title: CH-0008 Workflow platform design baseline
---

# Statement

The system shall apply a team role only to the resources of the team that grants it.

# Acceptance criteria

- A user who is `approver` in team A and `member` in team B gets B's resources at the `member` level only. A's approver-only skills, tools and sources are not visible in B, and B's are not unlocked by A.
- A team skill, tool grant or argument limit that names a role is satisfied only by that role held in the same team.
- The classification ceiling of a team role applies only to that team's sources. Platform sources use the ceiling of the platform roles.
- `whoami(explain=true)` and `sdlc-config explain` show each team role together with its team.
- The persona matrix has a cross-team persona (approver in one team, member in another), and the tests pin the expected access.

# Notes

Today the resolver merges every team's roles into one set, so a team role leaks across teams: for skills gated by role, for sources gated by role, and for the classification ceiling. That is a defect against this requirement once approved. [CH-0009](../../changes/CH-0009.md) fixes it. Connected tools are not affected: they use the user's own credentials, so dependent-system access is already user-scoped.
