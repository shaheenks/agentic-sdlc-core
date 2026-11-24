---
type: Functional Requirement
title: "Sub-agents"
description: "An agent step can use isolated sub-agents declared by the workflow."
tags: [requirement, agent-steps]
status: draft
x-area: AGT
x-priority: should
x-implementation: planned
---

# Statement

The system shall let an agent step run the sub-agents its workflow declares, such as isolated reviewers or parallel workers, under the same identity and limits.

# Acceptance criteria

- Sub-agents get no tools beyond their parent step's.
- Sub-agent token use counts toward the run's limits.
