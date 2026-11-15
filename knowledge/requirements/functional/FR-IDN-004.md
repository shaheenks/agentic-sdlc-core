---
type: Functional Requirement
title: Revocation of access
description: A blocked user loses access on the next request and their stored connections are removed by a reconcile job.
area: Identity
tags:
- requirement
- functional
- identity
status: draft
priority: must
implementation: live
sources:
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
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
- GCP stack: removing a user from a Google group revokes the roles it gave within `identity.google.group_cache_seconds`.

# Notes

Modified by [CH-0021](../../changes/CH-0021.md): per stack (Entra / GCP), design N7 to N10 and N13.
