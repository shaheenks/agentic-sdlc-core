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
verified:
- by: human:shaheenks
  at: '2026-11-11T16:02:28+05:30'
priority: should
implementation: live
sources:
- id: design
  resource: ../../../docs/designs/workflow-platform.md
  title: Workflow platform target design
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

The system shall expose the assistant to other agent platforms over the A2A protocol, acting for the signed-in user.

# Acceptance criteria

- `/a2a` speaks A2A 0.3 (JSON-RPC) and a public agent card is served at `/.well-known/agent-card.json`.
- Tasks and contexts are checked against their owner.
- Gemini Enterprise and every third-party agent platform (for example Microsoft Copilot) call `/a2a` with the user's own Entra token; a request without a valid user token is refused, and there is no platform or service token.

# Notes

Modified by CH-0008 (design D5). Gemini Enterprise is live on this path; other platforms use the same path and are checked when onboarded.

Cards built from tool results, never by the model, with forged cards dropped, are stated once, in [NFR-SEC-009](../non-functional/NFR-SEC-009.md), which covers the chat as well as A2A (CH-0002).
