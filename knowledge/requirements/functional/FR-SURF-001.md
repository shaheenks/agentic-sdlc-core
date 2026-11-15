---
type: Functional Requirement
title: Chat application
description: A web chat is the main surface for talking to the assistant.
area: Surfaces
tags:
- requirement
- functional
- surfaces
status: draft
priority: must
implementation: live
sources:
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: arch
  resource: ../../../docs/ARCHITECTURE.md
  title: System architecture
---

# Statement

The system shall provide a web chat in which users talk to the assistant and see its results in purpose-built views.

# Acceptance criteria

- The chat is served at `/chat/` behind sign-in and talks AG-UI to the agent: its `/agui` endpoint locally and on
  the Entra stack, the agent on Agent Runtime on the native GCP stack, with the same cards and threads.
- Results render as citation chips, artifact cards, review cards and connected-tool cards.
- The chat app stores no conversations itself.

# Notes

Modified by [CH-0016](../../changes/CH-0016.md): the chat on Agent Runtime (native stack).
