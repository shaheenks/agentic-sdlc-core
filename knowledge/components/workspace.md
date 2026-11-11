---
type: Component
title: workspace
description: 'The uv workspace root: explicit member list, shared lint and test settings, and the lock file.'
area: Delivery
tags:
- component
- delivery
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../pyproject.toml
satisfies:
- /requirements/non-functional/NFR-MAINT-001
verified_by:
- tests/infra/test_workspace.py
---

# Purpose

Makes every component an explicit workspace member and fixes the shared tool settings.

Code: `pyproject.toml`

# Responsibilities

- `[tool.uv.workspace] members` lists every Python component.
- Shared ruff and pytest configuration.

# Depends on

No other component.

# Requirements

- [NFR-MAINT-001: Modular workspace](../requirements/non-functional/NFR-MAINT-001.md) - Lists each component as a member; shared code is consumed from `libs/` as workspace packages.

# Verification

- `tests/infra/test_workspace.py`
