---
type: Non-Functional Requirement
title: "End-to-end trace per run"
description: "One trace follows a run through every step, model call and tool call."
tags: [requirement, observability]
status: draft
x-area: OBS
x-priority: must
x-implementation: planned
---

# Statement

The system shall produce one trace per run, with a span for each step, model call and tool call, correlated with audit events by trace ID.

# Acceptance criteria

- Opening a run's trace shows each step, model call and tool call with timing.
- Every audit event of the run carries the run's trace ID.
