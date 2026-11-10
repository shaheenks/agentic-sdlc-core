---
type: Functional Requirement
title: Reviewed document flow
description: Documents are produced by brainstorm, confirmed brief, draft, isolated reviewers and resolution, then saved with their review.
area: Documents
tags:
- requirement
- functional
- documents
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
- id: v03
  resource: ../../../docs/plans/version-03.md
  title: Implementation plan version-03
---

# Statement

The system shall produce documents through a flow of brainstorm, confirmed brief, draft, independent review and resolution.

# Acceptance criteria

- The confirmed brief locks the team for the document.
- Reviewers run in isolation from the drafting context and their findings are graded Blocker, Major or Nit.
- The document and its review are saved as artifacts.
