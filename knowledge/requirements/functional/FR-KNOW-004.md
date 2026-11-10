---
type: Functional Requirement
title: PDF ingestion
description: PDFs are ingested with page-level citations; OCR is opt-in per source.
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
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

The system shall ingest PDF documents, cite page ranges, and apply model OCR only to sources that opt in.

# Acceptance criteria

- The text layer is read with pypdf; chunks store page ranges and results return `pages`.
- OCR runs only for sources with `spec.ingest.pdf.ocr: gemini` and its output is cached.

# Notes

The text layer is live; OCR is built and awaits a live check on a source with scanned PDFs (version-03 P8).
