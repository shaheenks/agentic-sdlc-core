---
type: Non-Functional Requirement
title: Bounded data retention
description: Conversations and artifacts are kept for a limited, configured time.
area: Privacy
tags:
- requirement
- non-functional
- privacy
status: stable
priority: should
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:30:44+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
---

# Statement

User conversations and artifacts shall be kept only for a configured retention period.

# Acceptance criteria

- Conversations: 7-day idle retention locally; a time-to-live from conversation start on GCP.
- Artifacts: `SDLC_ARTIFACT_RETENTION_DAYS` (7), applied as the bucket lifecycle on GCP.
