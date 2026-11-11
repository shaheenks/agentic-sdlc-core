---
type: Functional Requirement
title: Workflow identity
description: Autonomous workflows authenticate with their own Entra workload identity and are authorized like any principal.
area: Identity
tags:
- requirement
- functional
- identity
status: draft
priority: must
implementation: planned
sources:
- id: design
  resource: ../../../docs/designs/workflow-platform.md
  title: Workflow platform target design
- id: change
  resource: ../../changes/CH-0008.md
  title: CH-0008 Workflow platform design baseline
---

# Statement

The system shall authenticate each autonomous workflow with its own Entra app-only identity and authorize it through the same policy as users.

# Acceptance criteria

- The MCP server accepts an app-only token only when it carries an app role bound to a workflow role. Any other app token gets 401.
- A workflow principal gets exactly its role's tools, sources and team. It never receives or forwards a user token.
- Audit records mark the principal kind (`user` or `workflow`) and the workflow id.
- On GCP, workflows use federated credentials, not client secrets.

# Notes

Design: version-03 P6 A1. Replaces part of FR-AUTO-001.
