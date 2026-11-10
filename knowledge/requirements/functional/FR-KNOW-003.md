---
type: Functional Requirement
title: Knowledge graph queries
description: Users can follow relations between entities extracted from their sources.
area: Knowledge
tags:
- requirement
- functional
- knowledge
status: stable
priority: should
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:13:57+05:30'
sources:
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

The system shall extract entities and relations per source and let users walk them at query time.

# Acceptance criteria

- `graph_query` seeds from vector and keyword matches and walks one or two hops.
- Entities and edges are stored per source and joined by key at query time, never across sources at write time.
- The walk returns only rows the caller may read.
