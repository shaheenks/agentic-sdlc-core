---
type: Functional Requirement
title: "Many teams per user"
description: "A user can belong to any number of teams and user groups, and sees what any of them grants."
tags: [requirement, teams]
status: draft
x-area: TEAM
x-priority: must
x-implementation: planned
---

# Statement

The system shall let a user belong to any number of teams and user groups, and make available to them every
workflow, skill and tool that any of those teams or groups, or everyone, is granted.

# Acceptance criteria

- A user in several teams sees the union of what their teams, their user groups and everyone are granted, minus
  anything explicitly denied to them.
- Each workflow in a list shows the teams it is available through.
- A run uses one team context ([FR-TEAM-002](FR-TEAM-002.md)), chosen from the teams that grant its workflow, or none.
