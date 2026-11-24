---
type: Functional Requirement
title: "Team parameter overrides"
description: "A team overrides only the parameters a global workflow declares as overridable; teams cannot fork workflows."
tags: [requirement, workflows]
status: draft
x-area: WFL
x-priority: should
x-implementation: planned
---

# Statement

The system shall let a team override the parameters a global workflow declares as overridable, and nothing else.

# Acceptance criteria

- Overrides are declared in configuration for the team and validated against the workflow's declared parameters.
- A team cannot declare its own variant or fork of a workflow.
- Runs for that team use the team's overrides.
