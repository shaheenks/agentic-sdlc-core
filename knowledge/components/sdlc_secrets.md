---
type: Component
title: sdlc_secrets
description: Secret references resolved at runtime from the environment or Secret Manager, with a short cache.
area: Libraries
tags:
- component
- libraries
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../libs/sdlc_secrets
satisfies:
- /requirements/non-functional/NFR-SEC-007
verified_by:
- tests/secrets
- tests/config/test_check_secrets.py
sources:
- id: readme
  resource: ../../libs/sdlc_secrets/README.md
  title: libs/sdlc_secrets/README.md
---

# Purpose

Configuration names a secret and never holds its value; this library resolves the reference when it is needed.

Code: `libs/sdlc_secrets`

# Responsibilities

- `{env: X}` and `{secret: x}` references.
- Stores: environment and Google Secret Manager.
- Five-minute cache per reference.

# Depends on

No other component.

# Requirements

- [NFR-SEC-007: Secrets handling](../requirements/non-functional/NFR-SEC-007.md) - Resolves references so values never appear in configuration.

# Verification

- `tests/secrets`
- `tests/config/test_check_secrets.py`
