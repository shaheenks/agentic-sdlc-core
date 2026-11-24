---
type: Component
title: "operations_agent"
description: "The event-based agent for operations: follows deployments, triages alerts with log analysis, and reports incidents and bugs back into the flow."
tags: [component, execution, events]
status: draft
x-layer: execution
x-folder: event_based_agents/operations_agent/
x-depends-on: [/components/agent-runtime, /components/event-agent-mcp, /components/skill-library, /components/observability]
x-satisfies: [/requirements/functional/FR-TRIG-005, /requirements/functional/FR-TRIG-003, /requirements/functional/FR-IDN-004, /requirements/non-functional/NFR-OBS-003, /requirements/non-functional/NFR-ARCH-003, /requirements/non-functional/NFR-ARCH-005, /requirements/non-functional/NFR-HOST-001, /requirements/functional/FR-SDLC-001, /requirements/functional/FR-SDLC-008, /requirements/functional/FR-SDLC-009, /requirements/functional/FR-SDLC-010, /requirements/functional/FR-SDLC-012]
---

# Purpose

Handles deployment and platform events ([FR-TRIG-005](../requirements/functional/FR-TRIG-005.md)): follows builds and rollouts ([FR-SDLC-008](../requirements/functional/FR-SDLC-008.md)), diagnoses alerts from logs, metrics and traces ([FR-SDLC-009](../requirements/functional/FR-SDLC-009.md)), and records incidents and bugs that can re-enter the flow as new work ([FR-SDLC-010](../requirements/functional/FR-SDLC-010.md)).

# Responsibilities

- Take a deployment or platform event (build or rollout started, succeeded or failed; an alert) and its metadata
  as the run's input.
- Diagnose read-only; act only through runbooks declared as pre-approved for the environment.
- Create or update incident and bug records in the declared tracker, without duplicates.
- Act as the system identity, the event agents' Agent Runtime service account, and call tools only through
  [event_agent_mcp](event-agent-mcp.md).
- Deliver results back to the downstream systems the workflow declares; keep nothing a user would have to look up.
- Carry the event metadata and trace context on every call ([NFR-OBS-003](../requirements/non-functional/NFR-OBS-003.md)).

# Out of scope

- Receiving and verifying events: the [Event Gateway](event-gateway.md).
- Anything owned by a user; work for users runs on the interactive deployment.

# Interfaces

- Provides: an ADK agent (graph workflow) started by the event gateway with the event as input.
- Consumes: event_agent_mcp tools, skills, models.

# Depends on

- [Agent Runtime](agent-runtime.md)
- [event_agent_mcp](event-agent-mcp.md)
- [Skill Library](skill-library.md)
- [Observability](observability.md)

# Owns

- Nothing durable; run state lives in its Agent Runtime session.

# Requirements

- [FR-TRIG-005: Deployment and platform events](../requirements/functional/FR-TRIG-005.md)
- [FR-TRIG-003: Results of unattended runs go back to the systems involved](../requirements/functional/FR-TRIG-003.md)
- [FR-IDN-004: System identity for unattended runs](../requirements/functional/FR-IDN-004.md)
- [NFR-OBS-003: Event metadata on every trace of an unattended run](../requirements/non-functional/NFR-OBS-003.md)
- [NFR-ARCH-003: Self-contained components](../requirements/non-functional/NFR-ARCH-003.md)
- [NFR-ARCH-005: Google ADK agents and graph workflows](../requirements/non-functional/NFR-ARCH-005.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [FR-SDLC-001: Approved artifact chain](../requirements/functional/FR-SDLC-001.md)
- [FR-SDLC-008: Deployment handling](../requirements/functional/FR-SDLC-008.md)
- [FR-SDLC-009: Alert triage and log analysis](../requirements/functional/FR-SDLC-009.md)
- [FR-SDLC-010: Incident and bug reporting](../requirements/functional/FR-SDLC-010.md)
- [FR-SDLC-012: Jira tasks from findings](../requirements/functional/FR-SDLC-012.md)

# Realisation

- First scope (development project): the platform's own services (sdlc_ui, user_agent_mcp, event_agent_mcp,
  a2a_router, knowledge_search, event_gateway) and its Cloud Run jobs (code_workspace, knowledge ingest). A pilot
  team's service is added once diagnoses prove reliable.
- First alerts, from Cloud Monitoring through Pub/Sub: Cloud Run 5xx error rate, Cloud Run p95 latency above
  5 s, Cloud Build failures, Cloud Deploy rollout failures or revisions that fail to become ready, and Cloud Run
  job execution failures.
- Tracker: Jira only, the team's project, for incident and bug records and tasks.
- Runbooks: none pre-approved for now; the agent diagnoses and reports only. Rolling Cloud Run traffic back to the
  previous ready revision in development is the first candidate, once diagnoses prove reliable.
- Python Google ADK agent in `event_based_agents/operations_agent/`, deployed with the other event agents to their own Agent Runtime deployment in
  europe-west3 ([DEC-0007](../decisions/DEC-0007.md)), separate from the interactive deployment.
