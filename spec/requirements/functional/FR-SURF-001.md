---
type: Functional Requirement
title: "Custom UI"
description: "Users run and follow workflows in the platform's own web UI, sdlc_ui."
tags: [requirement, surfaces]
status: draft
x-area: SURF
x-priority: must
x-implementation: planned
---

# Statement

The system shall provide a custom web UI, sdlc_ui, where a signed-in user can browse the workflows they may run, start a run for themselves or a team, follow its progress, answer human tasks and open the run's artifacts.

# Acceptance criteria

- A signed-in user sees only the workflows their effective policy allows.
- Starting a workflow validates the inputs against the workflow's input schema before a run is created.
- A run's step progress and agent output appear in the UI while the run executes, without reloading the page.
- The inbox lists the open human tasks of the user's own runs.
- The artifacts of a run the user may read can be previewed and downloaded.
