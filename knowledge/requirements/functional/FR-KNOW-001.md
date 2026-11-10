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
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:13:57+05:30'
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

- Source types: local folder, git (pinned SHA or tracked branch), GCS, Confluence and Jira.
- Unchanged content is skipped by hash and data of dropped sources is removed.
- Items that are natively restricted in the source system are never ingested.

# Notes

Git on GitHub, GCS and local folders are live. Confluence, Jira and Bitbucket remotes are built against fake APIs and not yet checked live (inventory gap 6).
