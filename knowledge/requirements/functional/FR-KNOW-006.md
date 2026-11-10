---
type: Functional Requirement
title: Atlassian and Bitbucket sources
description: Confluence spaces, Jira projects and Bitbucket repositories, Cloud and Data Center, can be declared and ingested as sources.
area: Knowledge
tags:
- requirement
- functional
- knowledge
status: draft
priority: should
implementation: planned
sources:
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: v03
  resource: ../../../docs/plans/version-03.md
  title: Implementation plan version-03 (P8)
- id: change
  resource: ../../changes/CH-0001.md
  title: CH-0001 Separate built capabilities from live ones
---

# Statement

The system shall ingest Confluence spaces, Jira projects and Bitbucket repositories, on Atlassian Cloud and on Data Center, when they are declared as sources.

# Acceptance criteria

- Confluence and Jira source types load pages and issues, and results cite a deep link to the page or issue.
- A git source may point at a Bitbucket Cloud or Bitbucket Data Center remote.
- Items that are natively restricted in the source system are never ingested.
- Each source type has been ingested once against a real site, recorded in the plan (version-03 P8).

# Notes

Split out of [FR-KNOW-001](FR-KNOW-001.md) by [CH-0001](../../changes/CH-0001.md). The code is built and tested against fake APIs only (inventory gap 6). `implementation` is `planned` while this concept is a draft and becomes `built` when CH-0001 is done; it becomes `live` after the P8 live check.
