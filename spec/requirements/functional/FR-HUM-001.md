---
type: Functional Requirement
title: "Human tasks pause a run"
description: "A run waits for a person to approve, review, choose or supply input."
tags: [requirement, human-tasks]
status: draft
x-area: HUM
x-priority: must
x-implementation: planned
---

# Statement

The system shall pause a run at a human-task step until a person answers it, and resume the run with the answer.

# Acceptance criteria

- Task kinds include approve or reject, review with comments, provide input and choose an option.
- A waiting run holds no compute while it waits.
- The answer is passed to the next step as the task step's output.

# Notes

Realised with ADK human input nodes, which pause the graph durably ([DEC-0004](../../decisions/DEC-0004.md)).
