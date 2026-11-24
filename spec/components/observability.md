---
type: Component
title: Observability
description: Traces, metrics and logs across a run - from trigger through agent steps and tool calls to data stores - without sensitive content.
tags: [component, platform]
status: draft
x-layer: platform
x-depends-on: []
x-satisfies: [/requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-PRIV-001, /requirements/non-functional/NFR-OBS-001, /requirements/non-functional/NFR-OBS-002, /requirements/non-functional/NFR-OBS-003, /requirements/functional/FR-MDL-002]
---

# Purpose

Lets operators and workflow authors see where a run spent time, tokens and money, and why it failed.

# Responsibilities

- One trace per run, with a span per step, model call and tool call, correlated with audit events by trace ID.
- Metrics: runs started, succeeded and failed per workflow; step latency; tokens and cost; human-task wait time.
- Structured logs with run and request IDs.
- Keep prompts, responses, tokens and argument values out of telemetry by default.

# Out of scope

- The authoritative security record: the [Audit Log](audit-log.md).

# Interfaces

- Provides: telemetry export (OpenTelemetry), dashboards for operators and workflow authors.

# Depends on

- None.

# Owns

- Telemetry under its retention policy.

# Requirements

- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-PRIV-001: No sensitive content in telemetry](../requirements/non-functional/NFR-PRIV-001.md)
- [NFR-OBS-001: End-to-end trace per run](../requirements/non-functional/NFR-OBS-001.md)
- [NFR-OBS-002: Operational metrics](../requirements/non-functional/NFR-OBS-002.md)
- [NFR-OBS-003: Event metadata on every trace of an unattended run](../requirements/non-functional/NFR-OBS-003.md)
- [FR-MDL-002: Usage and budgets](../requirements/functional/FR-MDL-002.md)

# Realisation

- Standard OpenTelemetry traces, metrics and logs; no per-run step transcripts for workflow authors.
