---
type: Functional Requirement
title: "Start a run"
description: "A permitted user starts a run of a workflow for themselves or a team from any surface."
tags: [requirement, workflows]
status: draft
x-area: WFL
x-priority: must
x-implementation: planned
---

# Statement

The system shall let a user who may start a workflow start a run of it, for themselves or a team, from any surface.

# Acceptance criteria

- Permission is checked before the run is created; a denied start is audited.
- The run records workflow version, configuration version, starter, team context, surface and inputs.
