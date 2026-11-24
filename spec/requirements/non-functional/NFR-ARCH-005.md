---
type: Non-Functional Requirement
title: "Google ADK agents and graph workflows"
description: "Agents are built with Google ADK and workflows are ADK graph workflows, deployed to Agent Runtime."
tags: [requirement, architecture]
status: draft
x-area: ARCH
x-priority: must
x-implementation: planned
---

# Statement

The system shall build its agents with Google ADK, on the latest stable ADK release, implement its multi-step
workflows as ADK graph workflows, and deploy them to Agent Runtime.

# Acceptance criteria

- Each catalog workflow is an ADK graph workflow; code-based dynamic workflows are used only where loops or
  branching do not fit a graph.
- Durable state, human input and resumption use ADK and Agent Runtime features (graph scheduler, human input
  nodes, Agent Runtime Sessions) rather than custom code.
- The ADK version is pinned in `interactive_agents/user_agent/` and upgraded deliberately.

# Notes

Accepted as [DEC-0004](../../decisions/DEC-0004.md).
