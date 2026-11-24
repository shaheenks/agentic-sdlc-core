---
type: Functional Requirement
title: "Teams declared in configuration"
description: "A user's teams, team roles and user groups are declared per environment in configuration."
tags: [requirement, teams]
status: draft
x-area: TEAM
x-priority: must
x-implementation: planned
---

# Statement

The system shall take a user's teams, team roles and user groups from the users declared in each environment's configuration.

# Acceptance criteria

- Each environment lists its users by email with their teams (a team alone gives its member role, or a named role) and user groups.
- A user who is not listed belongs to no team and no user group.
- A team, role or user group that is not declared is refused when the configuration is validated.
- Adding or removing a member takes effect once the changed configuration is activated, with no code change.
- Teams and membership are declared only in configuration; the platform offers no way to change them.
- Each team declaration names its owners.
- Each team declaration also names its Jira project, its Confluence spaces, and its repositories, any number of them (with the path for design specifications).

# Notes

Reading membership from Cloud Identity groups provisioned from Entra ID is deferred ([DEC-0010](../../decisions/DEC-0010.md)).
