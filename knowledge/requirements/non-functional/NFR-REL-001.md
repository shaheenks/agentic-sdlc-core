---
type: Non-Functional Requirement
title: Safe configuration reload
description: A bad configuration never replaces a good one, and each request sees one consistent version.
area: Reliability
tags:
- requirement
- non-functional
- reliability
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:45:18+05:30'
sources:
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

The system shall keep serving the last valid configuration when a new one fails to load, and evaluate each request against a single version.

# Acceptance criteria

- Reload keeps the last-known-good configuration.
- One configuration snapshot is taken per request; policy is never cached across versions.
- Rollback is done by moving the `current` pointer.
