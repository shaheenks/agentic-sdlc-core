---
type: Functional Requirement
title: Revocation of access
description: A blocked user loses access on the next request and their stored connections are removed by a reconcile job.
area: Identity
tags:
- requirement
- functional
- identity
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:10:40+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
---

# Statement

The system shall let operators block a user so that the next request is refused, and shall remove stored credentials that are no longer valid.

# Acceptance criteria

- A user in `blocked.yaml` gets 401 on the next MCP request, audited with reason `blocked`.
- `sdlc-reconcile-connections` is a dry run by default; with `--apply` it deletes PATs of blocked users, expired and long-rejected tokens and removed connections.
- Each reconcile change is audited as `connection_change` with `actor: reconcile`.
