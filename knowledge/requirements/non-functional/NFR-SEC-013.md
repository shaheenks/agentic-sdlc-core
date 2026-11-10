---
type: Non-Functional Requirement
title: Agents hold no write credentials
description: Agents emit structured outcomes; a separate delivery service holds the credentials that write to external systems.
area: Security
tags:
- requirement
- non-functional
- security
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

An agent that reads untrusted content shall not hold credentials that write to external systems.

# Acceptance criteria

- Workflow runtimes emit a typed, size-capped outcome, and only the delivery service posts it.
- Delivery posts only the fields the workflow's channel schema allows, to the target the Trigger names.
- Delivery credentials are reporting-only and scoped per channel.

# Notes

User-confirmed write tools (FR-WRITE-001) act as the user, with the user's confirmation. This requirement covers autonomous workflows.
