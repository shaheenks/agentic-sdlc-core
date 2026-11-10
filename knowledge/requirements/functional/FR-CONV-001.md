---
type: Functional Requirement
title: Conversation history
description: Users can list, reopen and delete their own conversations.
area: Conversations
tags:
- requirement
- functional
- conversations
status: stable
priority: should
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:28:01+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
---

# Statement

The system shall keep each user's conversations and let them list, reopen and delete their own.

# Acceptance criteria

- `GET /threads` returns only the caller's sessions.
- Opening a thread replays it as the same user.
- `DELETE /threads/{id}` deletes the caller's own chat; another user's or a missing thread answers 404.
