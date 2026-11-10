---
type: Component
title: sdlc_policy
description: Authorization decisions for MCP tools as pure functions over an effective policy, plus the rate limiter.
area: Libraries
tags:
- component
- libraries
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../libs/sdlc_policy
satisfies:
- /requirements/functional/FR-AUTHZ-001
- /requirements/functional/FR-AUTHZ-002
- /requirements/functional/FR-AUTHZ-004
- /requirements/non-functional/NFR-SEC-001
- /requirements/non-functional/NFR-SEC-002
verified_by:
- tests/policy/test_authorize.py
- tests/policy/test_rate_limits.py
- tests/policy/test_matrix.py
sources:
- id: readme
  resource: ../../libs/sdlc_policy/README.md
  title: libs/sdlc_policy/README.md
---

# Purpose

Decides whether a tool is visible and whether a call with given arguments is allowed. Deny by default.

Code: `libs/sdlc_policy`

# Responsibilities

- `visible_tools` and `authorize` (grant, deny, argument constraints).
- Sliding-window per-user rate limiter.

# Depends on

- [sdlc_config](sdlc_config.md)

# Requirements

- [FR-AUTHZ-001: Selective disclosure of tools](../requirements/functional/FR-AUTHZ-001.md) - `visible_tools`.
- [FR-AUTHZ-002: Per-call authorization with argument limits](../requirements/functional/FR-AUTHZ-002.md) - `authorize` with argument constraints.
- [FR-AUTHZ-004: Per-user rate limits](../requirements/functional/FR-AUTHZ-004.md) - Rate limiter.
- [NFR-SEC-001: Single enforcement point](../requirements/non-functional/NFR-SEC-001.md) - Holds the decision logic the MCP server enforces.
- [NFR-SEC-002: Deny by default](../requirements/non-functional/NFR-SEC-002.md) - Allows only what is granted and not denied.

# Verification

- `tests/policy/test_authorize.py`
- `tests/policy/test_rate_limits.py`
- `tests/policy/test_matrix.py`
