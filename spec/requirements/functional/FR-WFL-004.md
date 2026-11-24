---
type: Functional Requirement
title: "Durable runs"
description: "A run survives restarts and can be resumed, retried or cancelled."
tags: [requirement, workflows]
status: draft
x-area: WFL
x-priority: must
x-implementation: planned
---

# Statement

The system shall persist run state after each step so that a run survives restarts and can be resumed, a failed step retried, or the run cancelled.

# Acceptance criteria

- Restarting the engine during a run loses no completed step, and the run continues.
- The run's own user can retry a failed step; runs are visible to no one else ([FR-AUTHZ-008](FR-AUTHZ-008.md)).
- Cancelling stops the run before its next step and records who cancelled it.

# Notes

Run state is kept by the ADK graph scheduler in Agent Runtime Sessions ([DEC-0003](../../decisions/DEC-0003.md), [DEC-0004](../../decisions/DEC-0004.md)).
