---
type: Functional Requirement
title: Implementation workflow
description: An approved design or spec starts a sandboxed coding agent that delivers a first version of the code as a draft PR.
area: Workflows
tags:
- requirement
- functional
- workflows
status: draft
priority: could
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

The system shall, when a design or spec is approved, produce a first version of the code changes in a sandbox and deliver them as a draft pull request for human review.

# Acceptance criteria

- The trigger is an approved or merged spec PR, or a Jira transition, made by a person who holds `approver` on the team. Any other approval starts nothing.
- The agent drafts a plan from the spec and its change record before it changes code, and the plan is part of the PR.
- The coding agent is a Google ADK agent, and the run happens in a sandbox as NFR-SEC-012 specifies.
- The result is a draft PR that links the spec, the plan and the test results. The agent cannot approve or merge it.
- After merge, a drift check compares the code with the spec and reports gaps.

# Notes

The coding agent is built on Google ADK and runs on Google Cloud (Cloud Run Jobs), decided 2026-11-11 (design D2).
