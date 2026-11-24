---
type: Component
title: Gemini Enterprise Agent
description: The platform's agent deployment on Gemini Enterprise Platform, registered in the Gemini Enterprise app so users run workflows from Gemini Enterprise directly.
tags: [component, experience]
status: draft
x-layer: experience
x-folder: interactive_agents/user_agent/
x-depends-on: [/components/identity, /components/workflow-catalog, /components/workflow-engine, /components/human-tasks, /components/artifact-store, /components/a2a-router]
x-satisfies: [/requirements/functional/FR-SURF-003, /requirements/functional/FR-SURF-004, /requirements/functional/FR-IDN-001, /requirements/functional/FR-WFL-003, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-HOST-005, /requirements/non-functional/NFR-ARCH-002, /requirements/non-functional/NFR-ARCH-005, /requirements/non-functional/NFR-REL-001, /requirements/non-functional/NFR-OPS-001, /requirements/functional/FR-WFL-009, /requirements/functional/FR-AGT-005]
---

# Purpose

Brings the workflow catalog into the Gemini Enterprise app, where many users already work. Users talk
to this agent; it starts and follows runs for them and acts with their identity.

# Responsibilities

- List the workflows the user may start, and help them pick one and supply its inputs in conversation.
- Start runs on the [Workflow Engine](workflow-engine.md) as the user, and report progress and results with links to artifacts in [sdlc_ui](sdlc-ui.md).
- Let the user answer human tasks raised by their runs from the conversation.
- Make every platform call with the token Gemini Enterprise passes for the signed-in user. When there is none, refuse; never fall back to its own service identity.

# Out of scope

- Executing workflow steps: the [Agent Runtime](agent-runtime.md) does that, wherever it runs.
- Registering the agent in the Gemini Enterprise app: an administrator action outside the platform.

# Interfaces

- Provides: an agent deployment on Gemini Enterprise Platform, registered in the Gemini Enterprise app.
- Consumes: the [Workflow Catalog](workflow-catalog.md) list, the [Workflow Engine](workflow-engine.md) run API, [Human Tasks](human-tasks.md) APIs.

# Depends on

- [Identity](identity.md)
- [Workflow Catalog](workflow-catalog.md)
- [Workflow Engine](workflow-engine.md)
- [Human Tasks](human-tasks.md)
- [Artifact Store](artifact-store.md)
- [A2A Router](a2a-router.md)

# Owns

- Conversation state of the Gemini Enterprise sessions.

# Requirements

- [FR-SURF-003: Gemini Enterprise app](../requirements/functional/FR-SURF-003.md)
- [FR-SURF-004: Same behaviour on every surface](../requirements/functional/FR-SURF-004.md)
- [FR-IDN-001: Sign-in with Cloud Identity, federated from Entra ID](../requirements/functional/FR-IDN-001.md)
- [FR-WFL-003: Start a run](../requirements/functional/FR-WFL-003.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-HOST-005: Single region europe-west3](../requirements/non-functional/NFR-HOST-005.md)
- [NFR-ARCH-002: Hostnames and service URLs are configuration](../requirements/non-functional/NFR-ARCH-002.md)
- [NFR-ARCH-005: Google ADK agents and graph workflows](../requirements/non-functional/NFR-ARCH-005.md)
- [NFR-REL-001: 99.5% availability](../requirements/non-functional/NFR-REL-001.md)
- [NFR-OPS-001: Reproducible images](../requirements/non-functional/NFR-OPS-001.md)
- [FR-WFL-009: Resume after signing in again](../requirements/functional/FR-WFL-009.md)
- [FR-AGT-005: Ad-hoc knowledge search and brainstorm chat](../requirements/functional/FR-AGT-005.md)

# Realisation

- A deployment on Gemini Enterprise Platform Agent Runtime in europe-west3, registered in the organisation's Gemini Enterprise app, which runs in the `eu` multi-region.
- Registered as one A2A agent whose endpoint is the [A2A Router](a2a-router.md), for the whole catalog and ad-hoc
  chat; no agent per workflow or per team. Every agent step and chat runs in the one user_agent deployment on
  [Agent Runtime](agent-runtime.md), which is part of Gemini Enterprise Agent Platform.
- The registration carries an OAuth authorization (an OAuth client of the organisation, with the `openid` and
  `email` scopes), so Gemini Enterprise passes the signed-in user's token to the router.
- Part of the ADK application in folder `interactive_agents/user_agent/` ([DEC-0004](../decisions/DEC-0004.md)).
