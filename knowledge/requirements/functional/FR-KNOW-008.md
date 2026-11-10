---
type: Functional Requirement
title: Source code graph
description: Repositories are parsed into a symbol graph that queries can walk under the same access rules.
area: Knowledge
tags:
- requirement
- functional
- knowledge
status: draft
priority: should
implementation: planned
sources:
- id: design
  resource: ../../../docs/designs/workflow-platform.md
  title: Workflow platform target design
- id: change
  resource: ../../changes/CH-0008.md
  title: CH-0008 Workflow platform design baseline
---

# Statement

The system shall build a graph of code symbols and their relations from ingested repositories and let callers query it within their access.

# Acceptance criteria

- Supported languages parse into files, modules, classes and functions, with import, call and ownership relations.
- Code entities are stored per source and joined at query time, like the document graph.
- `graph_query` and a code-specific query can answer which symbols a change affects. Results cite the file and lines.
- A caller gets only code-graph rows from sources they may read.
