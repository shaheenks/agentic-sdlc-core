---
type: Non-Functional Requirement
title: Every decision is audited
description: Each authorization decision and data access produces one structured audit record.
area: Auditability
tags:
- requirement
- non-functional
- auditability
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:45:18+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
---

# Statement

The system shall write one structured audit record for every authorization decision, listing, access and credential change.

# Acceptance criteria

- Records are JSON lines on the `sdlc.audit` logger with one `event` each.
- Events: `tool_call`, `tools_list`, `skill_access`, `skills_list`, `artifact_change`, `artifact_access`, `connection_change` and `auth_failure`.
- A `tool_call` record carries who, teams, roles, tool, decision, matched rule and outcome.
- Failures record an error type and a message of at most 500 characters.
