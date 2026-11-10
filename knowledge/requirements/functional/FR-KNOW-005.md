---
type: Functional Requirement
title: Scheduled ingest
description: Ingest runs on a schedule in the cloud environment.
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
---

# Statement

The system shall refresh ingested knowledge on a schedule without manual action.

# Acceptance criteria

- On GCP, Cloud Scheduler starts the ingest Cloud Run job.
