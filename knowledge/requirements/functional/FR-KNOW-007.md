---
type: Functional Requirement
title: OCR for scanned PDFs
description: PDFs without a text layer are read with model OCR, only for sources that opt in.
area: Knowledge
tags:
- requirement
- functional
- knowledge
status: draft
priority: could
implementation: planned
sources:
- id: v03
  resource: ../../../docs/plans/version-03.md
  title: Implementation plan version-03 (P8)
- id: change
  resource: ../../changes/CH-0001.md
  title: CH-0001 Separate built capabilities from live ones
---

# Statement

The system shall extract text from scanned PDF pages with model OCR for sources that opt in, and from no other source.

# Acceptance criteria

- OCR runs only for sources with `spec.ingest.pdf.ocr: gemini`.
- OCR output is cached, so an unchanged PDF is not sent to the model again.
- Chunks from OCR pages keep their page ranges, as text-layer chunks do.
- A source with scanned PDFs has been ingested once with OCR on GCP dev, recorded in the plan (version-03 P8).

# Notes

Split out of [FR-KNOW-004](FR-KNOW-004.md) by [CH-0001](../../changes/CH-0001.md). `implementation` is `planned` while this concept is a draft and becomes `built` when CH-0001 is done; it becomes `live` after the P8 live check.
