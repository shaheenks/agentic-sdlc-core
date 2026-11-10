---
type: Non-Functional Requirement
title: External content is untrusted
description: Content from providers, sources and model extraction is treated as data, never as instructions or trusted structure.
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
  resource: ../../rules/index.md
  title: Project rules (rule sets)
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
---

# Statement

Content that originates outside the system shall be treated as untrusted data.

# Acceptance criteria

- Provider content returned by connected tools is handled as untrusted data.
- Graph extraction output is cleaned before it is stored.
- UI cards are built from tool results, never by the model, and forged cards are dropped.
