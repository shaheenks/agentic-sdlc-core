---
type: Functional Requirement
title: Per-user memory
description: The assistant keeps long-term memory per user, readable only in that user's sessions.
area: Conversations
tags:
- requirement
- functional
- conversations
status: draft
priority: could
implementation: parked
sources:
- id: design
  resource: ../../../docs/designs/workflow-platform.md
  title: Workflow platform target design
- id: change
  resource: ../../changes/CH-0008.md
  title: CH-0008 Workflow platform design baseline
---

# Statement

The system shall keep long-term memory for each user that only that user's sessions can read.

# Acceptance criteria

- Memory is written and read with the user's identity, and is never read by another user or by a workflow principal.
- A user can list and delete their memories.
- Memory follows the retention rules for conversations (NFR-PRIV-004).

# Notes

Parked 2026-11-11 (design D7): memory is optional, and only sessions are used now. If adopted, it uses the managed Memory service of the Gemini Enterprise agent platform.
