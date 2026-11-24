---
type: Functional Requirement
title: "Run limits"
description: "Each run stops when it exceeds its declared time, cost or step limits."
tags: [requirement, workflows]
status: draft
x-area: WFL
x-priority: must
x-implementation: planned
---

# Statement

The system shall stop a run that exceeds the duration, token, cost or step limits its workflow declares.

# Acceptance criteria

- Every workflow declares its limits, or inherits declared defaults.
- A run over a limit ends with status `limit_exceeded` and names the limit.
