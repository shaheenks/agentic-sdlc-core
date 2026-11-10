---
type: Functional Requirement
title: Agent-to-agent endpoint
description: Other agent platforms reach the assistant over A2A with the user's token.
area: Surfaces
tags:
- requirement
- functional
- surfaces
status: stable
priority: should
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:28:01+05:30'
sources:
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
---

# Statement

The system shall expose the assistant to other agent platforms over the A2A protocol, acting for the signed-in user.

# Acceptance criteria

- `/a2a` speaks A2A 0.3 (JSON-RPC) and a public agent card is served at `/.well-known/agent-card.json`.
- Tasks and contexts are checked against their owner.
- Tool results carry A2UI cards built from the result, never by the model; forged cards are dropped.
