---
type: Non-Functional Requirement
title: "Audit every decision"
description: "Every authentication, authorization decision, run start, human decision and activation is audited."
tags: [requirement, auditability]
status: draft
x-area: AUD
x-priority: must
x-implementation: planned
---

# Statement

The system shall record an audit event for every authentication failure, authorization decision, run start, human-task answer and configuration activation.

# Acceptance criteria

- Each event names actor, action, resource, decision, matched rule, configuration version and run and step where they apply.
- Audit events for one run can be listed by run ID.
