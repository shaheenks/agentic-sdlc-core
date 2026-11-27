---
type: Component
title: Event Gateway
description: Starts workflow runs from schedules and from events in downstream systems, such as a pull request opened or a ticket moved.
tags: [component, execution, workflow]
status: draft
x-layer: execution
x-folder: event_gateway/
x-depends-on: [/components/workflow-engine, /components/workflow-catalog, /components/identity, /components/audit-log, /components/secrets, /components/ci-workflow-agent, /components/operations-agent]
x-satisfies: [/requirements/functional/FR-IDN-004, /requirements/functional/FR-TRIG-001, /requirements/functional/FR-TRIG-002, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-ARCH-002, /requirements/non-functional/NFR-ARCH-003, /requirements/non-functional/NFR-OPS-002, /requirements/non-functional/NFR-SEC-004, /requirements/functional/FR-TRIG-004, /requirements/functional/FR-TRIG-005, /requirements/non-functional/NFR-OBS-003, /requirements/functional/FR-SDLC-006, /requirements/functional/FR-SDLC-007, /requirements/functional/FR-SDLC-008, /requirements/functional/FR-SDLC-009, /requirements/functional/FR-SDLC-011, /requirements/functional/FR-TRIG-006]
---

# Purpose

Many SDLC workflows should start without anyone clicking: review a PR when it opens, draft release
notes on a tag, triage a new defect. This component turns schedules and events into runs.

# Responsibilities

- Receive and verify webhooks from downstream systems; poll where webhooks are unavailable.
- Receive CI workflow events (for ci_workflow_agent) and deployment and platform service events (for
  operations_agent), the latter through Pub/Sub.
- Start the run's trace with the event metadata ([NFR-OBS-003](../requirements/non-functional/NFR-OBS-003.md)).
- Triage each event by its metadata (source system and edition, event type, repository, branch or path, Jira
  keys, project or service) against the subscriptions that workflows and teams have declared, and route it to
  the matching workflow of ci_workflow_agent or operations_agent.
- Run schedules (cron-style) declared for workflows and teams.
- Start each matched run as the system identity, with the event or schedule metadata attached ([FR-IDN-004](../requirements/functional/FR-IDN-004.md)); deduplicate repeat deliveries.
- Audit every event received, matched, ignored or rejected.
- Until the webhooks are set up, take simulated events from sdlc_ui for a member of a team the environment allows
  to simulate; read the pull request's facts from the provider and run the event like a verified delivery, marked
  simulated with the user who sent it ([FR-TRIG-006](../requirements/functional/FR-TRIG-006.md),
  [DEC-0016](../decisions/DEC-0016.md)).

# Out of scope

- Running the workflow: the [Workflow Engine](workflow-engine.md).

# Interfaces

- Provides: webhook endpoints per provider; subscription and schedule status; `/simulate` for sdlc_ui.
- Consumes: subscriptions in the [Workflow Catalog](workflow-catalog.md); the run API of the engine.

# Depends on

- [Workflow Engine](workflow-engine.md)
- [Workflow Catalog](workflow-catalog.md)
- [Identity](identity.md)
- [Audit Log](audit-log.md)
- [Secrets](secrets.md)
- [ci_workflow_agent](ci-workflow-agent.md)
- [operations_agent](operations-agent.md)

# Owns

- Subscription state, schedule state, received-event log for deduplication.

# Requirements

- [FR-IDN-004: System identity for unattended runs](../requirements/functional/FR-IDN-004.md)
- [FR-TRIG-001: Event triggers](../requirements/functional/FR-TRIG-001.md)
- [FR-TRIG-002: Schedules](../requirements/functional/FR-TRIG-002.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-ARCH-002: Hostnames and service URLs are configuration](../requirements/non-functional/NFR-ARCH-002.md)
- [NFR-ARCH-003: Self-contained components](../requirements/non-functional/NFR-ARCH-003.md)
- [NFR-OPS-002: Local Docker Compose environment](../requirements/non-functional/NFR-OPS-002.md)
- [NFR-SEC-004: Where secrets live](../requirements/non-functional/NFR-SEC-004.md)
- [FR-TRIG-004: CI workflow events](../requirements/functional/FR-TRIG-004.md)
- [FR-TRIG-005: Deployment and platform events](../requirements/functional/FR-TRIG-005.md)
- [FR-TRIG-006: Simulated events](../requirements/functional/FR-TRIG-006.md)
- [NFR-OBS-003: Event metadata on every trace of an unattended run](../requirements/non-functional/NFR-OBS-003.md)
- [FR-SDLC-006: Implementation by ci_workflow_agent](../requirements/functional/FR-SDLC-006.md)
- [FR-SDLC-007: Security vulnerability analysis of pull requests](../requirements/functional/FR-SDLC-007.md)
- [FR-SDLC-008: Deployment handling](../requirements/functional/FR-SDLC-008.md)
- [FR-SDLC-009: Alert triage and log analysis](../requirements/functional/FR-SDLC-009.md)
- [FR-SDLC-011: Quality assurance analysis of pull requests](../requirements/functional/FR-SDLC-011.md)

# Realisation

- Webhook receiver on Cloud Run in europe-west3; schedules from Cloud Scheduler (proposed).
- Webhook signing secrets and any other secrets as environment variables from Secret Manager (Cloud Run secret
  references); it mounts no bucket of secrets.
- Folder `event_gateway/`, self-contained; deduplicates deliveries by creating one object per delivery ID only if absent ([DEC-0003](../decisions/DEC-0003.md)).
- Built ([DEC-0015](../decisions/DEC-0015.md), phase 5a milestone 3): `POST /webhooks/github` verifies
  `X-Hub-Signature-256` first, triages by metadata against `subscriptions.yaml` for the system identity's teams,
  claims each matched delivery with a create-if-absent object under `events/deliveries/` and queues one Cloud Task
  per subscription; `POST /run` accepts only the queue's OIDC token, creates the run's Agent Runtime session once
  (`events/runs/`, so a retry continues it) and follows the run. Bitbucket and Jira webhooks and schedules come
  later.
