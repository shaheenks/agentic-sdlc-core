---
type: Non-Functional Requirement
title: Retrieval quality gate
description: Changes to retrieval are kept only if the retrieval evaluation does not get worse.
area: Quality
tags:
- requirement
- non-functional
- quality
status: stable
priority: should
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:45:18+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
- id: v03
  resource: ../../../docs/plans/version-03.md
  title: Implementation plan version-03
---

# Statement

A change to retrieval shall be kept only if the retrieval evaluation improves or holds.

# Acceptance criteria

- The retrieval eval (`tests/evals`) compares vector and hybrid search on the ingested development database.
- Repository questions are re-checked after merges, because the platform source tracks `main`.
