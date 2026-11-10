---
type: Non-Functional Requirement
title: Access rules are covered by tests
description: A new tool, source or team cannot be added without the tests that pin its access.
area: Maintainability
tags:
- requirement
- non-functional
- maintainability
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

Every tool, source and team shall be covered by tests that pin who can use it.

# Acceptance criteria

- A test fails if a catalog tool has no persona-matrix rows.
- A new source has persona-matrix `data_rows`.
- A test enforces a CODEOWNERS rule for each new team, team skill folder and source.
