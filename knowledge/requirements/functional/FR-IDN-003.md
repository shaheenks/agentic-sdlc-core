---
type: Functional Requirement
title: Users can see their own access
description: A user can ask what they are allowed to do and why; only admins can view another user's policy.
area: Identity
tags:
- requirement
- functional
- identity
status: stable
priority: should
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:10:40+05:30'
sources:
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
---

# Statement

The system shall let each user view their own effective access with the rules that grant it, and shall restrict viewing another identity's policy to admins.

# Acceptance criteria

- `whoami(explain=true)` shows only the caller's own view, including source rules.
- `config_explain(groups, app_roles)` is available to the admin role only.
