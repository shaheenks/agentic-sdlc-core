---
type: Functional Requirement
title: Workflows are declared and classified
description: Each workflow is declared in configuration with its class, trigger, identity, access and outcome delivery.
area: Workflows
tags:
- requirement
- functional
- workflows
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

The system shall run every workflow from a declaration that names its class, its source events, the identity it runs as, the systems it may reach and where its outcome is delivered.

# Acceptance criteria

- A `Workflow` config kind names the class (`plan-design`, `build-test`, `deploy-maintain`, `implementation`), the agent definition, its skills, its principal, its autonomy tier and its delivery channel.
- `sdlc-config validate` rejects a Workflow whose principal, skills, tools or channel are not declared, or whose tier is `act`.
- A new workflow needs only configuration, an agent definition and skills. Platform code changes only for a new event adapter, connector or delivery channel.
- `sdlc-config explain` shows a workflow principal's effective tools, sources and team, as for a user.

# Notes

Class `plan-design` is the user-led flow built today. Its declaration describes it and grants nothing beyond the user's own policy.
