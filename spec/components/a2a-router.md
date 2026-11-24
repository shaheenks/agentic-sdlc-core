---
type: Component
title: "A2A Router"
description: "One A2A router in front of user_agent, used by Gemini Enterprise now and by third-party A2A surfaces such as Microsoft Copilot once enabled, acting as the calling user."
tags: [component, experience]
status: draft
x-layer: experience
x-folder: a2a_router/
x-depends-on: [/components/identity, /components/workflow-catalog, /components/workflow-engine, /components/artifact-store, /components/agent-runtime]
x-satisfies: [/requirements/functional/FR-SURF-002, /requirements/functional/FR-SURF-004, /requirements/functional/FR-SURF-005, /requirements/functional/FR-IDN-001, /requirements/functional/FR-WFL-003, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-ARCH-002, /requirements/non-functional/NFR-ARCH-005, /requirements/non-functional/NFR-REL-001, /requirements/non-functional/NFR-PERF-001, /requirements/non-functional/NFR-OPS-001, /requirements/functional/FR-AGT-005, /requirements/functional/FR-SURF-003]
---

# Purpose

The one A2A entry point to user_agent. Gemini Enterprise reaches the platform through it now; third-party A2A
surfaces such as Microsoft Copilot (through Copilot Studio) use the same router once they are enabled
([FR-SURF-005](../requirements/functional/FR-SURF-005.md), parked). Every caller gets the same identity and
permissions the user has in [sdlc_ui](sdlc-ui.md).

# Responsibilities

- Implement the latest stable A2A protocol version (1.0 when this was written), declare it in the agent card and
  honour the `A2A-Version` header.
- Publish an agent card whose skills are the workflows; give an authenticated caller only the workflows they may start.
- Route each A2A message to user_agent: a workflow run (pick the workflow, collect its inputs, start the run as
  the caller) or ad-hoc chat ([FR-AGT-005](../requirements/functional/FR-AGT-005.md)).
- Report a run as an A2A task: status updates while it runs, input-required while it waits on the caller,
  artifacts on completion.
- Declare an OAuth 2.0 security scheme (Google's authorization and token endpoints) in the agent card.
- Know each third-party surface by its OAuth client, as declared in configuration, and record it on every run.
- Refuse any request without a valid user identity.

# Out of scope

- Running the workflow: the [Workflow Engine](workflow-engine.md).
- Registering the router in the Gemini Enterprise app: the [Gemini Enterprise Agent](gemini-enterprise-agent.md).
- Coding harnesses such as Google Antigravity: [user_agent_mcp](user-agent-mcp.md).

# Interfaces

- Provides: an A2A router (agent card, message send and stream, task get and cancel).
- Consumes: user_agent on [Agent Runtime](agent-runtime.md) (queried with the router's service account, the
  user's token passed along for user_agent's calls to user_agent_mcp), the [Workflow Catalog](workflow-catalog.md)
  list, the [Workflow Engine](workflow-engine.md) run API, artifact links.

# Depends on

- [Identity](identity.md)
- [Workflow Catalog](workflow-catalog.md)
- [Workflow Engine](workflow-engine.md)
- [Artifact Store](artifact-store.md)
- [Agent Runtime](agent-runtime.md)

# Owns

- Mapping between A2A task IDs and run IDs.

# Requirements

- [FR-SURF-002: A2A router](../requirements/functional/FR-SURF-002.md)
- [FR-SURF-004: Same behaviour on every surface](../requirements/functional/FR-SURF-004.md)
- [FR-SURF-005: Third-party AI surfaces over A2A](../requirements/functional/FR-SURF-005.md)
- [FR-IDN-001: Sign-in with Cloud Identity, federated from Entra ID](../requirements/functional/FR-IDN-001.md)
- [FR-WFL-003: Start a run](../requirements/functional/FR-WFL-003.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-ARCH-002: Hostnames and service URLs are configuration](../requirements/non-functional/NFR-ARCH-002.md)
- [NFR-ARCH-005: Google ADK agents and graph workflows](../requirements/non-functional/NFR-ARCH-005.md)
- [NFR-REL-001: 99.5% availability](../requirements/non-functional/NFR-REL-001.md)
- [NFR-PERF-001: Application response under 5 seconds on average](../requirements/non-functional/NFR-PERF-001.md)
- [NFR-OPS-001: Reproducible images](../requirements/non-functional/NFR-OPS-001.md)
- [FR-AGT-005: Ad-hoc knowledge search and brainstorm chat](../requirements/functional/FR-AGT-005.md)
- [FR-SURF-003: Gemini Enterprise app](../requirements/functional/FR-SURF-003.md)

# Realisation

- On Google Cloud in europe-west3, public HTTPS, not behind Identity-Aware Proxy: clients present Google OAuth
  tokens, which [Identity](identity.md) verifies on every request.
- A small Python Cloud Run service in folder `a2a_router/`, in front of the user_agent deployment on Agent
  Runtime, so callers need no IAM permission on Agent Runtime. Only the router's service account may query that
  deployment; the user's identity travels as the verified user token, which user_agent forwards to
  user_agent_mcp, so every tool call is still made as the user.
- Uses ADK's A2A support where it implements the chosen protocol version.
