---
type: Functional Requirement
title: "Approval before writes"
description: "Write actions on downstream systems run only after an approval where the workflow requires one."
tags: [requirement, human-tasks]
status: draft
x-area: HUM
x-priority: must
x-implementation: planned
---

# Statement

The system shall run a tool classed as a write only after an approved human task, where the workflow requires one, and show the approver exactly what will be written.

# Acceptance criteria

- Every tool is classed as read or write in the tool registry.
- Where approval is required, the MCP server refuses a write that lacks an approval bound to the same run, step and payload.
- The approver, the run's own user, sees the payload that will be written.
- In unattended runs, which have no approver, only writes declared as allowed without approval for the system identity can run.
- For writes to Jira, Confluence or product repositories in the SDLC flow, the approval bound to the write is the
  merge of the artifact's pull request on the team's control repository, checked by the MCP server
  ([FR-SDLC-013](FR-SDLC-013.md), [DEC-0012](../../decisions/DEC-0012.md) (accepted)).
