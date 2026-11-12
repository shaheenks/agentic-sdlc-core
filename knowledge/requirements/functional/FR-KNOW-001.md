---
type: Functional Requirement
title: Ingest declared sources
description: Sources declared in configuration are loaded, chunked, embedded and tagged with their source and classification.
area: Knowledge
tags:
- requirement
- functional
- knowledge
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-11T16:02:28+05:30'
priority: must
implementation: live
sources:
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: arch
  resource: ../../../docs/ARCHITECTURE.md
  title: System architecture
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

The system shall ingest the sources declared in configuration and tag every stored row with its source and classification.

# Acceptance criteria

- Source types: local folder, git on GitHub (pinned SHA or tracked branch) and GCS. Atlassian and Bitbucket sources are [FR-KNOW-006](FR-KNOW-006.md).
- Unchanged content is skipped by hash and data of dropped sources is removed.
- Items that are natively restricted in the source system are never ingested.

# Notes

Modified by CH-0001: the parts built but never checked live moved to FR-KNOW-006.
