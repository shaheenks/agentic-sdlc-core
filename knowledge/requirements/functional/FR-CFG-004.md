---
type: Functional Requirement
title: Admin view of the running configuration
description: Admins can inspect which configuration version a server is running.
area: Configuration
tags:
- requirement
- functional
- configuration
status: stable
priority: could
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

The system shall let admins inspect the configuration version a server is running.

# Acceptance criteria

- `config_info()` is available to the admin role only.
