---
type: Functional Requirement
title: Chat application
description: A web chat is the main surface for talking to the assistant.
area: Surfaces
tags:
- requirement
- functional
- surfaces
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:28:01+05:30'
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

- The chat is served at `/chat/` behind sign-in and talks AG-UI to the agent.
- Results render as citation chips, artifact cards, review cards and connected-tool cards.
- The chat app stores no conversations itself.
