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
- Egress is allowed only to the repository host, the model endpoint and declared package registries.
- The repository token is short-lived and can only push to a new branch. It cannot approve, merge or change branch protection.
- No production, database or user credential is present in the sandbox.
