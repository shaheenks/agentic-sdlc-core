---
type: Functional Requirement
title: Agent-to-agent endpoint
description: Other agent platforms reach the assistant over A2A with the user's token.
area: Surfaces
tags:
- requirement
- functional
- surfaces
status: draft
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
- Tool results carry A2UI cards built from the result, never by the model; forged cards are dropped.
- Gemini Enterprise and every third-party agent platform (for example Microsoft Copilot) call `/a2a` with the user's own Entra token; a request without a valid user token is refused, and there is no platform or service token.

# Notes

Modified by CH-0008 (design D5). Gemini Enterprise is live on this path; other platforms use the same path and are checked when onboarded.
