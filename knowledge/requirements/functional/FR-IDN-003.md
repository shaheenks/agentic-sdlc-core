---
type: Functional Requirement
title: Users can see their own access
description: A user can ask what they are allowed to do and why; only admins can view another user's policy.
area: Identity
tags:
- requirement
- functional
- identity
status: draft
priority: should
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

The system shall let each user view their own effective access with the rules that grant it, and shall restrict viewing another identity's policy to admins.

# Acceptance criteria

- `whoami(explain=true)` shows only the caller's own view, including source rules: the app-role or group binding, or the `users.yaml` entry, behind each role.
- `config_explain(app_roles, groups, user)` is available to the admin role only; `groups` takes Google group emails.

# Notes

Edited by CH-0011: the `groups` argument is removed.

Modified by [CH-0021](../../changes/CH-0021.md): per stack (Entra / GCP), design N7 to N10 and N13.
