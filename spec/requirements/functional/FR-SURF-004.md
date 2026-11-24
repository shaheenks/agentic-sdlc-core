---
type: Functional Requirement
title: "Same behaviour on every surface"
description: "A user gets the same workflows, permissions, runs and artifacts whichever surface they use."
tags: [requirement, surfaces]
status: draft
x-area: SURF
x-priority: must
x-implementation: planned
---

# Statement

The system shall give a user the same workflows, permissions, runs and artifacts on every surface.

# Acceptance criteria

- For a given user and team context, the startable workflows are the same in sdlc_ui, in Gemini Enterprise and over A2A, including from third-party AI surfaces ([FR-SURF-005](FR-SURF-005.md)), and over MCP ([FR-SURF-006](FR-SURF-006.md)).
- A run started on any surface appears in the user's run history in sdlc_ui, with the surface it was started from.
- Every surface gets its authorization decisions from the same component and configuration version.
