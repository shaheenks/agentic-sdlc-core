---
type: Non-Functional Requirement
title: "No sensitive content in telemetry"
description: "Logs, traces and metrics carry no prompts, responses, tokens or argument values."
tags: [requirement, privacy]
status: draft
x-area: PRIV
x-priority: must
x-implementation: planned
---

# Statement

The system shall keep prompts, model responses, tokens and tool argument values out of logs, traces, metrics and audit records.

# Acceptance criteria

- A test run's telemetry and audit records contain none of its prompts, responses or argument values.
