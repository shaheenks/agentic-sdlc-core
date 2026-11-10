---
type: Component
title: ci
description: 'The CI workflow and CODEOWNERS: lint, config validation and permission diff, knowledge bundle checks, UI checks, database tests and Terraform checks.'
area: Delivery
tags:
- component
- delivery
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../.github
satisfies:
- /requirements/functional/FR-CFG-002
- /requirements/non-functional/NFR-MAINT-002
- /requirements/non-functional/NFR-MAINT-003
- /requirements/non-functional/NFR-MAINT-004
- /requirements/non-functional/NFR-PORT-003
verified_by:
- tests/policy/test_codeowners.py
- tests/policy/test_matrix.py
---

# Purpose

Gates every change without secrets or cloud access, and routes reviews to owners.

Code: `.github`

# Responsibilities

- `workflows/ci.yml`: ruff, `sdlc-config validate`, permission diff on pull requests, knowledge bundle lint and drift hint, UI typecheck/test/build, tests on a pgvector service, Terraform fmt/validate.
- `CODEOWNERS`: a rule per team, team skill folder, source and security-critical path.

# Depends on

- [workspace](workspace.md)

# Requirements

- [FR-CFG-002: Explain and diff effective permissions](../requirements/functional/FR-CFG-002.md) - Publishes the permission diff on each pull request.
- [NFR-MAINT-002: Access rules are covered by tests](../requirements/non-functional/NFR-MAINT-002.md) - Runs the tests that require matrix rows and CODEOWNERS rules.
- [NFR-MAINT-003: CI runs without secrets](../requirements/non-functional/NFR-MAINT-003.md) - Runs with placeholders only: no secrets, no cloud calls.
- [NFR-MAINT-004: Permission changes are reviewable](../requirements/non-functional/NFR-MAINT-004.md) - Attaches the per-persona diff and routes review by CODEOWNERS.
- [NFR-PORT-003: Local and cloud parity](../requirements/non-functional/NFR-PORT-003.md) - Keeps `infra/gcp` valid with Terraform checks.

# Verification

- `tests/policy/test_codeowners.py`
- `tests/policy/test_matrix.py`
