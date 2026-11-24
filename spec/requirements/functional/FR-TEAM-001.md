---
type: Functional Requirement
title: "Teams from Cloud Identity groups"
description: "A user's teams and team roles come from Cloud Identity groups, provisioned from Entra ID and mapped in configuration."
tags: [requirement, teams]
status: draft
x-area: TEAM
x-priority: must
x-implementation: planned
---

# Statement

The system shall derive a user's teams and team roles from Cloud Identity groups, provisioned from Entra ID and mapped to teams in configuration.

# Acceptance criteria

- Membership, including through nested groups, is read from Cloud Identity, since Google tokens carry no groups.
- Adding a user to a mapped group in Entra ID makes them a team member once provisioning has run, with no platform change.
- A user in no mapped group belongs to no team.
- Each team declaration names its owners and the group emails that give membership and each team role.
- A group that cannot be resolved removes only the memberships that depend on it.
- Teams and membership are declared only in configuration; the platform offers no way to change them.
- Each team declaration also names its Jira project, its Confluence spaces, and its repositories, any number of them (with the path for design specifications).
