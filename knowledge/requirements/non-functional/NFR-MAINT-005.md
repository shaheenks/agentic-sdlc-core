---
type: Non-Functional Requirement
title: The specification is traced and checked
description: Every built requirement traces to components and every component to tests, and a tool checks the trace on every change.
area: Maintainability
tags:
- requirement
- non-functional
- maintainability
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-12T21:06:15+05:30'
priority: should
implementation: live
sources:
- id: conventions
  resource: ../../conventions.md
  title: Bundle conventions
- id: change
  resource: ../../changes/CH-0007.md
  title: CH-0007 Check the specification tooling
---

# Statement

The knowledge bundle shall trace every built requirement to the components that satisfy it and every component to the tests that verify it, and the trace shall be checked automatically on every change.

# Acceptance criteria

- `okf_bundle.py lint` runs in CI on every push and pull request, and inside `uv run pytest`.
- The lint fails when a `live`, `built` or `stub` requirement has no component.
- The lint fails when a `verified_by` path is not a test: it must sit in a `tests` folder or be a test file.
- The lint fails when a `live`, `built` or `stub` requirement that is not `deprecated` says `to be defined` in its acceptance criteria.
- `okf_bundle.py` has its own tests in `tests/knowledge`, and they run without the real bundle.

# Notes

Added by [CH-0007](../../changes/CH-0007.md). The rule that a `stable` concept needs a `human:` verification is already enforced.
