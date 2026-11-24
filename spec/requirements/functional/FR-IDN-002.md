---
type: Functional Requirement
title: "Act as the user end to end"
description: "Every tool call, data read and downstream call of a user's run is made as that user."
tags: [requirement, identity]
status: draft
x-area: IDN
x-priority: must
x-implementation: planned
---

# Statement

The system shall make every tool call, data read and downstream call of a run started by a user with that user's identity.

# Acceptance criteria

- Every tool call in the audit log names the user the run acts for.
- Knowledge reads are filtered by that user's data scope.
- User-initiated work reaches downstream systems through the user's own connection, never a shared service credential.

# Notes

Scheduled and event-triggered runs act as the system identity instead: [FR-IDN-004](FR-IDN-004.md).
