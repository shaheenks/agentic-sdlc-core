---
type: Functional Requirement
title: PDF ingestion
description: PDFs are ingested from their text layer with page-level citations.
area: Knowledge
tags:
- requirement
- functional
- knowledge
status: draft
priority: should
implementation: live
sources:
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

The system shall ingest PDF documents and cite page ranges.

# Acceptance criteria

- The text layer is read with pypdf; chunks store page ranges and results return `pages`.

# Notes

Modified by CH-0001: OCR for scanned pages moved to [FR-KNOW-007](FR-KNOW-007.md).
