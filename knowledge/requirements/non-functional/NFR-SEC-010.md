---
type: Non-Functional Requirement
title: Least-privilege runtime
description: Each service gets only the credentials and environment it needs.
area: Security
tags:
- requirement
- non-functional
- security
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:30:44+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
---

# Statement

Each service shall run with only the credentials, environment and database rights it needs.

# Acceptance criteria

- Only MCP servers and ingest get database credentials.
- Agent containers get an explicit environment allow-list, never the whole `.env`.
- Database roles are separated: `sdlc_owner` (migrations), `sdlc_app` (read-only except its own artifact rows) and `sdlc_ingest` (writes).
