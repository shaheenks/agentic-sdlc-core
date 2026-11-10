---
type: Non-Functional Requirement
title: Permission changes are reviewable
description: Every configuration change shows its effect on each persona before merge.
area: Maintainability
tags:
- requirement
- non-functional
- maintainability
status: stable
priority: should
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

Every configuration change shall show its effect on each persona's permissions before it is merged.

# Acceptance criteria

- The per-persona diff is attached to each config pull request.
- CODEOWNERS routes each team, team skill folder and source to its owners.
