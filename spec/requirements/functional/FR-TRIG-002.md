---
type: Functional Requirement
title: "Schedules"
description: "Runs start on schedules declared in configuration."
tags: [requirement, triggers]
status: draft
x-area: TRIG
x-priority: could
x-implementation: planned
---

# Statement

The system shall start runs on the schedules declared in configuration.

# Acceptance criteria

- A schedule names its workflow, inputs and team context; its runs act as the system identity.
- A missed schedule tick is either run once on recovery or skipped, as the schedule declares.
