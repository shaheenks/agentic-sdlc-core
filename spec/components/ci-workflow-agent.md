---
type: Component
title: "ci_workflow_agent"
description: "The event-based agent for code: turns a merged design specification into a plan and then a pull request, and runs two review workflows on pull requests: security vulnerability analysis and quality assurance analysis."
tags: [component, execution, events]
status: draft
x-layer: execution
x-folder: event_based_agents/ci_workflow_agent/
x-depends-on: [/components/agent-runtime, /components/event-agent-mcp, /components/skill-library, /components/observability, /components/code-workspace]
x-satisfies: [/requirements/functional/FR-TRIG-004, /requirements/functional/FR-TRIG-003, /requirements/functional/FR-IDN-004, /requirements/non-functional/NFR-OBS-003, /requirements/non-functional/NFR-ARCH-003, /requirements/non-functional/NFR-ARCH-005, /requirements/non-functional/NFR-HOST-001, /requirements/functional/FR-SDLC-001, /requirements/functional/FR-SDLC-006, /requirements/functional/FR-SDLC-007, /requirements/functional/FR-SDLC-011, /requirements/functional/FR-SDLC-012]
---

# Purpose

Picks up the work once a person merges the design specification pull request: proposes an implementation plan, then implements it as a pull request with tests ([FR-SDLC-006](../requirements/functional/FR-SDLC-006.md)). It runs two separate review workflows on every pull request in a declared repository: security vulnerability analysis ([FR-SDLC-007](../requirements/functional/FR-SDLC-007.md)) and quality assurance analysis ([FR-SDLC-011](../requirements/functional/FR-SDLC-011.md)). It also explains failed CI runs ([FR-TRIG-004](../requirements/functional/FR-TRIG-004.md)).

# Responsibilities

- Take a repository or CI event (design specification merged, plan merged, pull request opened or updated, CI run finished or
  failed) and its metadata as the run's input.
- Implementation: propose `plan.md`, and after it is merged implement it with tests on a branch and open a pull
  request; never merge, approve or push to a protected branch.
- Security vulnerability analysis and quality assurance analysis: two workflows, each with its own trigger,
  skills and configuration, run in fresh contexts on each pull request; never on the run that wrote the code.
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
- [Code Workspace](code-workspace.md)

# Owns

- Nothing durable; run state lives in its Agent Runtime session.

# Requirements

- [FR-TRIG-004: CI workflow events](../requirements/functional/FR-TRIG-004.md)
- [FR-TRIG-003: Results of unattended runs go back to the systems involved](../requirements/functional/FR-TRIG-003.md)
- [FR-IDN-004: System identity for unattended runs](../requirements/functional/FR-IDN-004.md)
- [NFR-OBS-003: Event metadata on every trace of an unattended run](../requirements/non-functional/NFR-OBS-003.md)
- [NFR-ARCH-003: Self-contained components](../requirements/non-functional/NFR-ARCH-003.md)
- [NFR-ARCH-005: Google ADK agents and graph workflows](../requirements/non-functional/NFR-ARCH-005.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [FR-SDLC-001: Approved artifact chain](../requirements/functional/FR-SDLC-001.md)
- [FR-SDLC-006: Implementation by ci_workflow_agent](../requirements/functional/FR-SDLC-006.md)
- [FR-SDLC-007: Security vulnerability analysis of pull requests](../requirements/functional/FR-SDLC-007.md)
- [FR-SDLC-011: Quality assurance analysis of pull requests](../requirements/functional/FR-SDLC-011.md)
- [FR-SDLC-012: Jira tasks from findings](../requirements/functional/FR-SDLC-012.md)

# Realisation

- Python Google ADK agent in `event_based_agents/ci_workflow_agent/`, deployed with the other event agents to their own Agent Runtime deployment in
  europe-west3 ([DEC-0007](../decisions/DEC-0007.md)), separate from the interactive deployment.
- Code is edited and tests are run in the [Code Workspace](code-workspace.md), a Cloud Run job started through event_agent_mcp; the agent sends its changes, reads the results and iterates within the run's limits.
