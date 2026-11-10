---
type: Non-Functional Requirement
title: CI runs without secrets
description: The full CI suite runs with no secrets and no cloud calls.
area: Maintainability
tags:
- requirement
- non-functional
- maintainability
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
---

# Statement

Continuous integration shall run without secrets or calls to cloud services.

# Acceptance criteria

- Tests pass without `.env`, using placeholder Entra IDs, the example group map, a hash embedder and fake Entra tokens.
- CI covers lint, config validation, the permission diff, UI checks, database tests and Terraform checks.
