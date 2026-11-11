---
type: Non-Functional Requirement
title: Sandboxed code execution
description: Code written by agents runs only in ephemeral sandboxes with no production access.
area: Security
tags:
- requirement
- non-functional
- security
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

Agent-driven code changes and their builds shall run only in an ephemeral sandbox that cannot reach production systems or credentials.

# Acceptance criteria

- Each run is a fresh job that is destroyed afterwards.
- Egress is allowed only to the model endpoint and declared package registries.
- No external-system credential is present in the sandbox: no repository, Jira or Confluence token, and no production, database or user credential. Model access uses the job's own service account, which has only the model role.
- The checkout is prepared outside the sandbox before the run. The sandbox returns a patch, and a component outside the sandbox pushes a new branch and opens the draft PR through the MCP backend. Nothing in the run can approve, merge or change branch protection.
