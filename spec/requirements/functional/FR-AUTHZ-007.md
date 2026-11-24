---
type: Functional Requirement
title: "Grants to teams and user groups"
description: "Workflows, skills and tools are made available per team or per user group in configuration."
tags: [requirement, authorization]
status: draft
x-area: AUTHZ
x-priority: must
x-implementation: planned
---

# Statement

The system shall let configuration make each workflow, skill and tool group available to everyone, to named
teams, or to named user groups, and withhold it from everyone else.

# Acceptance criteria

- A user group is a Cloud Identity group declared in configuration, whether or not it is also a team.
- Granting a workflow to a team or user group, or removing the grant, is a configuration change only.
- A workflow, skill or tool group with no grant is available to no one.
