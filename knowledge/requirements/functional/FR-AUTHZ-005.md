---
type: Functional Requirement
title: Data access granted per source
description: Knowledge is readable only where the source's own access rule grants it, under the role's classification ceiling.
area: Authorization
tags:
- requirement
- functional
- authorization
status: draft
priority: must
implementation: live
sources:
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
- id: arch
  resource: ../../../docs/ARCHITECTURE.md
  title: System architecture
---

# Statement

The system shall grant access to knowledge only through each source's access rule, limited by the caller's classification ceiling.

# Acceptance criteria

- `Source.access` accepts `teams`, `roles` or `everyone: true`; nothing else grants data access. A source that needs its own audience grants a role bound to its own app role.
- A user outside a source's access rule gets no rows from it in search or graph results.

# Notes

Matrix `data_rows` and CODEOWNERS rules for new sources are stated once, in [NFR-MAINT-002](../non-functional/NFR-MAINT-002.md) and [NFR-MAINT-004](../non-functional/NFR-MAINT-004.md) (CH-0002).

Edited by CH-0011: `groups` is removed from `Source.access`.
