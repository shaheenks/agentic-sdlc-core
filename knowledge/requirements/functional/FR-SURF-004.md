---
type: Functional Requirement
title: Catalogs for coding harnesses
description: Coding harnesses get the caller's tools, skills and knowledge catalogs straight from the MCP server.
area: Surfaces
tags:
- requirement
- functional
- surfaces
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

The system shall expose to coding harnesses, directly from the MCP server, the tools, skills and knowledge sources the caller may use.

# Acceptance criteria

- Tools come from `tools/list`. Skills come from `list_skills` / `load_skill` and as MCP prompts or resources. Knowledge sources come from `list_sources`.
- `list_sources` returns only readable sources, with their type, classification and last ingest time.
- A harness signs the user in with Entra OAuth and sees exactly what the same user sees in the chat.
- Hidden skills, tools and sources are not disclosed (NFR-PRIV-002).

# Notes

Builds on FR-SURF-003. OAuth sign-in from harnesses is version-03 P9.
