---
type: Functional Requirement
title: "System identity for unattended runs"
description: "Scheduled and event-triggered runs act as the platform's system identity and carry the triggering event's metadata."
tags: [requirement, identity]
status: draft
x-area: IDN
x-priority: must
x-implementation: planned
---

# Statement

The system shall run every scheduled or event-triggered run as the platform's system identity, with only the permissions declared for it in configuration, and attach the metadata of the schedule or event that started it.

# Acceptance criteria

- The system identity is the service account of the event agents' own Agent Runtime deployment, used for nothing else; no key or token for it is stored anywhere.
- Its permissions are declared in configuration as a role and resolved by the Access Policy like any user's; it has no undeclared grant.
- An event-triggered run records the source system, event type, delivery ID, subject (for example the repository and pull request), the actor the event names, and the time received. A scheduled run records the schedule ID and tick time.
- The actor an event names is recorded for attribution only and never grants a permission.
- Audit records of an unattended run name the system identity as the actor and carry the trigger metadata.
- An unattended run has no user of its own, so its workflow declares no human tasks; a workflow with one cannot be triggered ([FR-HUM-002](FR-HUM-002.md)).
- Agents of an unattended run call tools only through event_agent_mcp ([FR-AGT-004](FR-AGT-004.md)).
- Every span, log entry, audit record and event_agent_mcp request of an unattended run carries the event metadata (source system, event type, delivery ID, subject) and the run ID ([NFR-OBS-003](../non-functional/NFR-OBS-003.md)).
