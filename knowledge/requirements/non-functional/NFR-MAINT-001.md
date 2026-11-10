---
type: Non-Functional Requirement
title: Modular workspace
description: Components are siblings in one workspace and shared code lives only in libraries.
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
  resource: ../../../CLAUDE.md
  title: Project rules
---

# Statement

New functionality shall be added as sibling components, with shared code in libraries and never copied.

# Acceptance criteria

- Every component is an explicit uv workspace member in the root `pyproject.toml`.
- Shared code lives in `libs/`.

# Notes

`ingest/chunkers`, `ingest/embedders` and `ingest/extractors` are placeholders; their code still lives in `ingest/bootstrap` (inventory gap 7).
