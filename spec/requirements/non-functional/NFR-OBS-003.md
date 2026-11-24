---
type: Non-Functional Requirement
title: "Event metadata on every trace of an unattended run"
description: "Scheduled and event-triggered runs are traced and audited with the triggering event's metadata, end to end."
tags: [requirement, obs, events]
status: draft
x-area: OBS
x-priority: must
x-implementation: planned
---

# Statement

The system shall attach the triggering event's metadata to every trace, log entry and audit record of a scheduled or event-triggered run, from the event gateway through the agents to event_agent_mcp and the downstream calls.

# Acceptance criteria

- In an unattended run, every span, log entry, audit record and event_agent_mcp request of an unattended run carries the event metadata (source system, event type, delivery ID, subject) and the run ID.
- The event gateway starts the trace; the agents and event_agent_mcp continue it (W3C trace context), so one trace covers the run.
- A delivery ID finds every record of its run in Cloud Trace and Cloud Logging.
- Event payloads are not copied into telemetry ([NFR-PRIV-001](NFR-PRIV-001.md)); only the metadata is.

# Notes

Event agents use their Google Cloud service account for identity and the event metadata for tracing.
