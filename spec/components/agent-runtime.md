---
type: Component
title: "Agent Runtime"
description: "Executes the agent nodes of a workflow with Google ADK on Agent Runtime - loads the node's skills, reasons with Gemini and calls tools through user_agent_mcp, as the user."
tags: [component, execution, agent]
status: draft
x-layer: execution
x-folder: interactive_agents/user_agent/
x-depends-on: [/components/skill-library, /components/user-agent-mcp, /components/observability, /components/event-agent-mcp]
x-satisfies: [/requirements/functional/FR-IDN-002, /requirements/functional/FR-AGT-001, /requirements/functional/FR-AGT-002, /requirements/functional/FR-AGT-003, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-ARCH-002, /requirements/non-functional/NFR-ARCH-003, /requirements/non-functional/NFR-ARCH-005, /requirements/non-functional/NFR-SEC-001, /requirements/non-functional/NFR-OBS-001, /requirements/non-functional/NFR-OPS-002, /requirements/functional/FR-AGT-005, /requirements/functional/FR-MDL-001, /requirements/non-functional/NFR-HOST-005]
---

# Purpose

Runs agent nodes for the [Workflow Engine](workflow-engine.md). Agents are built with Google ADK on the latest
stable release ([DEC-0004](../decisions/DEC-0004.md)). An agent has no privileges of its own: it sees only the tools
[user_agent_mcp](user-agent-mcp.md) lists for this identity and surface.

# Responsibilities

- Assemble the node context: instructions, the skills bound to the node, team instructions, the run's inputs and earlier outputs.
- Run the model loop with Gemini on Vertex AI, mapping the node's model class to a concrete model from
  configuration ([FR-MDL-001](../requirements/functional/FR-MDL-001.md)).
- Call every tool through [user_agent_mcp](user-agent-mcp.md), forwarding the user's access token as the bearer
  token (or the system identity's for unattended runs); never a service credential on a user's behalf.
- Return structured output matching the node's declared output schema; fail the node if it cannot.
- Support sub-agents (isolated reviewers, parallel workers) declared by the workflow.
- Make no authorization decisions; hold no database or downstream credentials.
- Run user_agent's ad-hoc knowledge search and brainstorm chat outside any workflow ([FR-AGT-005](../requirements/functional/FR-AGT-005.md)).

# Out of scope

- Ordering nodes and holding run state: the [Workflow Engine](workflow-engine.md).

# Interfaces

- Provides: agent nodes for ADK graph workflows; node progress events.
- Consumes: skills, MCP tool listings and calls, model completions.

# Depends on

- [Skill Library](skill-library.md)
- [user_agent_mcp](user-agent-mcp.md)
- [Observability](observability.md)
- [event_agent_mcp](event-agent-mcp.md)

# Owns

- Nothing durable; transcripts stay in the run's session.

# Requirements

- [FR-IDN-002: Act as the user end to end](../requirements/functional/FR-IDN-002.md)
- [FR-AGT-001: Bounded agent steps](../requirements/functional/FR-AGT-001.md)
- [FR-AGT-002: Sub-agents](../requirements/functional/FR-AGT-002.md)
- [FR-AGT-003: User agent MCP server](../requirements/functional/FR-AGT-003.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-ARCH-002: Hostnames and service URLs are configuration](../requirements/non-functional/NFR-ARCH-002.md)
- [NFR-ARCH-003: Self-contained components](../requirements/non-functional/NFR-ARCH-003.md)
- [NFR-ARCH-005: Google ADK agents and graph workflows](../requirements/non-functional/NFR-ARCH-005.md)
- [NFR-SEC-001: Authorization only in the platform's services](../requirements/non-functional/NFR-SEC-001.md)
- [NFR-OBS-001: End-to-end trace per run](../requirements/non-functional/NFR-OBS-001.md)
- [NFR-OPS-002: Local Docker Compose environment](../requirements/non-functional/NFR-OPS-002.md)
- [FR-AGT-005: Ad-hoc knowledge search and brainstorm chat](../requirements/functional/FR-AGT-005.md)
- [FR-MDL-001: Model classes](../requirements/functional/FR-MDL-001.md)
- [NFR-HOST-005: Single region europe-west3](../requirements/non-functional/NFR-HOST-005.md)

# Realisation

- Two Agent Runtime deployments: the interactive agents (`interactive_agents/`: user_agent; user tokens,
  user_agent_mcp), and the event agents (`event_based_agents/`: ci_workflow_agent, operations_agent), whose
  deployment service account is the system identity and which call only event_agent_mcp
  ([DEC-0007](../decisions/DEC-0007.md)).
- Python, Google ADK 2.x application in folder `interactive_agents/user_agent/`, deployed to Agent Runtime on Gemini Enterprise Agent
  Platform in europe-west3. The same folder holds the workflow graphs and the Gemini Enterprise agent.
- Gemini through Vertex AI with Application Default Credentials: the deployment's service account in Google
  Cloud, the developer's gcloud credentials locally.
- Every model, language and embedding, is called on Vertex AI at its europe-west3 endpoint, or `eu` where it has none; there is no separate model gateway.
