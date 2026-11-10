---
type: Non-Functional Requirement
title: Secrets handling
description: Secrets live only in the local env file or Secret Manager and are referenced, never embedded.
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

Secrets shall be stored only in the environment's secret store and appear elsewhere only as references.

# Acceptance criteria

- Configuration holds secret references (`{env: X}` / `{secret: x}`) resolved at runtime.
- Secrets never appear in config, URLs, logs, the database or config bundles.
- No secret is committed to the repository.
