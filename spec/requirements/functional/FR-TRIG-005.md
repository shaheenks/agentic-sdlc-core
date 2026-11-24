---
type: Functional Requirement
title: "Deployment and platform events"
description: "operations_agent handles events from deployment and platform services, such as a failed rollout or a platform alert, and reports back to the systems involved."
tags: [requirement, trig, events, operations]
status: draft
x-area: TRIG
x-priority: should
x-implementation: planned
---

# Statement

The system shall run operations_agent on events from deployment and platform services that match the subscriptions declared in configuration, and deliver its results to the systems the workflow declares.

# Acceptance criteria

- Declared sources (for example Cloud Build, Cloud Deploy, Cloud Run and Cloud Monitoring alerts, delivered through Pub/Sub) reach the event gateway, which verifies and deduplicates them ([FR-TRIG-001](FR-TRIG-001.md)).
- Each matched event starts one run of operations_agent on the event agents' Agent Runtime, acting as the system identity ([FR-IDN-004](FR-IDN-004.md)).
- Results go to the declared downstream systems, for example a ticket or a page ([FR-TRIG-003](FR-TRIG-003.md)).
- The run's traces carry the event metadata ([NFR-OBS-003](../non-functional/NFR-OBS-003.md)).

# Notes

The first event sources and actions are to be agreed.
