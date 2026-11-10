---
type: Functional Requirement
title: Knowledge search with citations
description: Users search their team's knowledge and get answers with citations to the exact place.
area: Knowledge
tags:
- requirement
- functional
- knowledge
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:13:57+05:30'
sources:
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
---

# Statement

The system shall let users search the knowledge they are allowed to read and return citations to the matching location.

# Acceptance criteria

- `search_knowledge` combines vector search with keyword matches on identifier terms.
- Results cite the file and lines, PDF pages, or a deep link.
- Results contain only rows the caller may read.
