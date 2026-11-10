---
type: Non-Functional Requirement
title: Records can be correlated
description: Audit records link to the request, conversation, trace and configuration version.
area: Auditability
tags:
- requirement
- non-functional
- auditability
status: stable
priority: should
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:45:18+05:30'
sources:
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

Audit records shall carry identifiers that link them to the request, the conversation, the trace and the configuration version in force.

# Acceptance criteria

- Every record carries `request_id` and `agent_session_id`; `trace_id` when tracing is on.
- `tool_call` records carry `config_version`.
