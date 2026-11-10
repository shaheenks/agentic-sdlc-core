---
type: Functional Requirement
title: Team resolution and lock
description: The assistant works broadly until a brief is confirmed, then locks to one of the user's own teams.
area: Teams
tags:
- requirement
- functional
- teams
status: stable
priority: should
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:13:57+05:30'
sources:
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

The system shall resolve which of the caller's teams a request concerns and lock that team for a document once its brief is confirmed.

# Acceptance criteria

- `resolve_team` sees only the caller's own teams; `get_agent_context` for another team answers 'unknown team'.
- The lock is held in server-side session state checked as the user; clients can never set `sdlc_` state keys.
- A direct member's `default_team` applies only while the user is a member.
