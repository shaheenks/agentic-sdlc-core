---
type: Functional Requirement
title: Data access granted per source
description: Knowledge is readable only where the source's own access rule grants it, under the role's classification ceiling.
area: Authorization
tags:
- requirement
- functional
- authorization
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:10:40+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
- id: arch
  resource: ../../../docs/ARCHITECTURE.md
  title: System architecture
---

# Statement

The system shall grant access to knowledge only through each source's access rule, limited by the caller's classification ceiling.

# Acceptance criteria

- `Source.access` accepts `teams`, `roles`, `groups` (the source's own group alias) or `everyone: true`; nothing else grants data access.
- A user outside a source's access rule gets no rows from it in search or graph results.
- A new source has persona-matrix `data_rows` and a CODEOWNERS rule.
