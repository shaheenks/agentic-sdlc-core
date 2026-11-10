---
type: Non-Functional Requirement
title: End-to-end tracing
description: One agent turn is one trace across the agent, the MCP server and Postgres.
area: Observability
tags:
- requirement
- non-functional
- observability
status: stable
priority: should
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

The system shall trace one agent turn end to end across the agent, the MCP server and the database.

# Acceptance criteria

- Trace context travels in MCP `_meta`, not in HTTP headers.
- Traces export to an OTLP endpoint locally and to Cloud Trace on GCP.
