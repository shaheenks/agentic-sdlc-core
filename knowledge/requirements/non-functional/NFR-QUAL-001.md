---
type: Non-Functional Requirement
title: Retrieval quality gate
description: Changes to retrieval are kept only if the retrieval evaluation does not get worse.
area: Quality
tags:
- requirement
- non-functional
- quality
status: draft
priority: should
implementation: live
sources:
- id: design
  resource: ../../../docs/designs/workflow-platform.md
  title: Workflow platform target design
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
- id: v03
  resource: ../../../docs/plans/version-03.md
  title: Implementation plan version-03
---

# Statement

A change to retrieval shall be kept only if the retrieval evaluation improves or holds.

# Acceptance criteria

- The retrieval eval (`tests/evals`) compares vector and hybrid search on the ingested development database.
- Repository questions are re-checked after merges, because the platform source tracks `main`.
- Every content type the system ingests (documents, PDFs, code graph, images, Office and structured data) has questions in the eval set before its retrieval change is kept.

# Notes

Modified by CH-0008: the knowledge extensions FR-KNOW-008 to FR-KNOW-010.
