---
type: Functional Requirement
title: "Artifact ownership"
description: "An artifact belongs to the user whose run produced it and is readable only by that user."
tags: [requirement, artifacts]
status: draft
x-area: ART
x-priority: must
x-implementation: planned
---

# Statement

The system shall give each artifact one owner, the user whose run produced it, and let only that owner list, read and delete it.

# Acceptance criteria

- A read by anyone else is answered as not found and audited ([FR-AUTHZ-008](FR-AUTHZ-008.md)).
- There is no sharing with teams or other users for now.
- Artifacts of scheduled and event-triggered runs belong to the system identity and are reached only through event_agent_mcp ([FR-AGT-004](FR-AGT-004.md)).

# Notes

There are no team artifacts or explicit sharing, for per-user isolation. Results of unattended runs go back to the downstream systems instead ([FR-TRIG-003](FR-TRIG-003.md)).
