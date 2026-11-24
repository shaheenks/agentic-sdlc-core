---
type: Functional Requirement
title: "Team runs visible to the team"
description: "Members of a team see the team's runs and artifacts as their team role allows."
tags: [requirement, teams]
status: draft
x-area: TEAM
x-priority: must
x-implementation: parked
---

# Statement

The system shall show a team's runs and their artifacts to the members of that team as their team role allows.

# Acceptance criteria

- Team members see the team's runs in sdlc_ui; non-members do not.
- What a member can do with a team run (view, retry, cancel) follows the grants of their team role.

# Notes

Parked: runs, sessions and artifacts are visible only to their own user ([FR-AUTHZ-008](FR-AUTHZ-008.md)). Reconsider together with team sharing of artifacts.
