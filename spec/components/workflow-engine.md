---
type: Component
title: "Workflow Engine"
description: "Runs catalog workflows durably for a user, a team or the system identity, as ADK 2.0 graph workflows on Agent Runtime with state in Agent Runtime Sessions."
tags: [component, execution, workflow]
status: draft
x-layer: execution
x-folder: interactive_agents/user_agent/
x-depends-on: [/components/workflow-catalog, /components/access-policy, /components/agent-runtime, /components/user-agent-mcp, /components/human-tasks, /components/artifact-store, /components/audit-log, /components/observability, /components/event-agent-mcp]
x-satisfies: [/requirements/functional/FR-SURF-001, /requirements/functional/FR-SURF-002, /requirements/functional/FR-SURF-003, /requirements/functional/FR-SURF-004, /requirements/functional/FR-SURF-005, /requirements/functional/FR-IDN-002, /requirements/functional/FR-IDN-003, /requirements/functional/FR-IDN-004, /requirements/functional/FR-TEAM-002, /requirements/functional/FR-TEAM-003, /requirements/functional/FR-AUTHZ-003, /requirements/functional/FR-AUTHZ-005, /requirements/functional/FR-WFL-003, /requirements/functional/FR-WFL-004, /requirements/functional/FR-WFL-005, /requirements/functional/FR-WFL-006, /requirements/functional/FR-WFL-008, /requirements/functional/FR-TRIG-001, /requirements/functional/FR-TRIG-002, /requirements/functional/FR-HUM-001, /requirements/functional/FR-HUM-005, /requirements/functional/FR-CONN-002, /requirements/functional/FR-ART-001, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-ARCH-003, /requirements/non-functional/NFR-ARCH-005, /requirements/non-functional/NFR-PRIV-002, /requirements/non-functional/NFR-OBS-001, /requirements/non-functional/NFR-REL-001, /requirements/non-functional/NFR-REL-002, /requirements/non-functional/NFR-PERF-001, /requirements/non-functional/NFR-OPS-002, /requirements/functional/FR-AUTHZ-008, /requirements/functional/FR-WFL-009, /requirements/functional/FR-TRIG-003]
---

# Purpose

The heart of the platform. A run is one execution of one workflow version, owned by the user who started it (or
the system identity) and optionally visible to a team. It is realised by the ADK graph scheduler, not a service
of its own ([DEC-0004](../decisions/DEC-0004.md)), and keeps its state in Agent Runtime Sessions, not a database ([DEC-0003](../decisions/DEC-0003.md)).

# Responsibilities

- Start a run: check with the [Access Policy](access-policy.md), through [user_agent_mcp](user-agent-mcp.md),
  that the caller may start this workflow in this team context; validate inputs; pin workflow and configuration versions.
- Execute the workflow graph: agent nodes on the [Agent Runtime](agent-runtime.md), tool nodes through
  [user_agent_mcp](user-agent-mcp.md) for a user's run or [event_agent_mcp](event-agent-mcp.md) for an unattended run, human input nodes through [Human Tasks](human-tasks.md), sub-workflows.
- Persist state after each node in the run's Agent Runtime session, so a run survives restarts and can resume,
  retry a node, or be cancelled.
- Key each run's session by the user ID and label it with workflow, version, team, surface and trigger; run
  history lists only the caller's own sessions ([FR-AUTHZ-008](../requirements/functional/FR-AUTHZ-008.md)).
- Resume a waiting run when its user answers, with the token of that request, also after signing in again
  ([FR-WFL-009](../requirements/functional/FR-WFL-009.md)).
- Enforce run limits (time, tokens, cost, node count) and stop a run that exceeds them.
- Carry the initiating identity (the user's token, or the system identity) through every node.
- Emit node-level progress events for live views and store outputs as artifacts through user_agent_mcp.

# Out of scope

- Model reasoning inside a node: the [Agent Runtime](agent-runtime.md).
- Deciding permissions: the [Access Policy](access-policy.md).

# Interfaces

- Provides: start, get, list, cancel, retry and resume for runs through the ADK application's API on Agent
  Runtime; a run event stream.
- Consumes: workflow graphs and catalog entries, node executors, human input answers.

# Depends on

- [Workflow Catalog](workflow-catalog.md)
- [Access Policy](access-policy.md)
- [Agent Runtime](agent-runtime.md)
- [user_agent_mcp](user-agent-mcp.md)
- [Human Tasks](human-tasks.md)
- [Artifact Store](artifact-store.md)
- [Audit Log](audit-log.md)
- [Observability](observability.md)
- [event_agent_mcp](event-agent-mcp.md)

# Owns

- Run state, held in Agent Runtime Sessions.

# Requirements

- [FR-SURF-001: Custom UI](../requirements/functional/FR-SURF-001.md)
- [FR-SURF-002: A2A router](../requirements/functional/FR-SURF-002.md)
- [FR-SURF-003: Gemini Enterprise app](../requirements/functional/FR-SURF-003.md)
- [FR-SURF-004: Same behaviour on every surface](../requirements/functional/FR-SURF-004.md)
- [FR-SURF-005: Third-party AI surfaces over A2A](../requirements/functional/FR-SURF-005.md)
- [FR-IDN-002: Act as the user end to end](../requirements/functional/FR-IDN-002.md)
- [FR-IDN-003: Block list](../requirements/functional/FR-IDN-003.md)
- [FR-IDN-004: System identity for unattended runs](../requirements/functional/FR-IDN-004.md)
- [FR-TEAM-002: Team context](../requirements/functional/FR-TEAM-002.md)
- [FR-TEAM-003: Team runs visible to the team](../requirements/functional/FR-TEAM-003.md)
- [FR-AUTHZ-003: Authorize every call](../requirements/functional/FR-AUTHZ-003.md)
- [FR-AUTHZ-005: Rate limits and quotas](../requirements/functional/FR-AUTHZ-005.md)
- [FR-WFL-003: Start a run](../requirements/functional/FR-WFL-003.md)
- [FR-WFL-004: Durable runs](../requirements/functional/FR-WFL-004.md)
- [FR-WFL-005: Run limits](../requirements/functional/FR-WFL-005.md)
- [FR-WFL-006: Reproducible runs](../requirements/functional/FR-WFL-006.md)
- [FR-WFL-008: Run events and history](../requirements/functional/FR-WFL-008.md)
- [FR-TRIG-001: Event triggers](../requirements/functional/FR-TRIG-001.md)
- [FR-TRIG-002: Schedules](../requirements/functional/FR-TRIG-002.md)
- [FR-HUM-001: Human tasks pause a run](../requirements/functional/FR-HUM-001.md)
- [FR-HUM-005: Approval before writes](../requirements/functional/FR-HUM-005.md)
- [FR-CONN-002: Reconnect instead of fail](../requirements/functional/FR-CONN-002.md)
- [FR-ART-001: Artifacts with lineage](../requirements/functional/FR-ART-001.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-ARCH-003: Self-contained components](../requirements/non-functional/NFR-ARCH-003.md)
- [NFR-ARCH-005: Google ADK agents and graph workflows](../requirements/non-functional/NFR-ARCH-005.md)
- [NFR-PRIV-002: Run transcripts under run access](../requirements/non-functional/NFR-PRIV-002.md)
- [NFR-OBS-001: End-to-end trace per run](../requirements/non-functional/NFR-OBS-001.md)
- [NFR-REL-001: 99.5% availability](../requirements/non-functional/NFR-REL-001.md)
- [NFR-REL-002: Multi-zone production](../requirements/non-functional/NFR-REL-002.md)
- [NFR-PERF-001: Application response under 5 seconds on average](../requirements/non-functional/NFR-PERF-001.md)
- [NFR-OPS-002: Local Docker Compose environment](../requirements/non-functional/NFR-OPS-002.md)
- [FR-AUTHZ-008: Per-user isolation of sessions, artifacts and secrets](../requirements/functional/FR-AUTHZ-008.md)
- [FR-WFL-009: Resume after signing in again](../requirements/functional/FR-WFL-009.md)
- [FR-TRIG-003: Results of unattended runs go back to the systems involved](../requirements/functional/FR-TRIG-003.md)

# Realisation

- ADK 2.x graph workflows in folder `interactive_agents/user_agent/`, deployed to Agent Runtime in europe-west3; state through
  ADK's Agent Runtime session service. Locally, the ADK application runs in Docker Compose against the
  development project's Agent Runtime Sessions or an in-memory session service, by profile.
- Agent steps are expected to finish within the user's session; a step cut short by an expired token resumes from the session history once the user signs in again ([FR-WFL-009](../requirements/functional/FR-WFL-009.md)).
