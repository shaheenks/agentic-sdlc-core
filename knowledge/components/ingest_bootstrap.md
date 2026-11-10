---
type: Component
title: ingest_bootstrap
description: 'The ingest pipeline and its CLI: chunk, embed, extract the graph and write changed documents.'
area: Pipelines
tags:
- component
- pipelines
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../ingest/bootstrap
satisfies:
- /requirements/functional/FR-KNOW-001
- /requirements/functional/FR-KNOW-003
- /requirements/functional/FR-KNOW-004
- /requirements/non-functional/NFR-REL-004
- /requirements/non-functional/NFR-SEC-009
verified_by:
- tests/ingest/test_chunker.py
- tests/ingest/test_graph_extract.py
- tests/ingest/test_pdf.py
- tests/db/test_pdf_ingest.py
sources:
- id: readme
  resource: ../../ingest/bootstrap/README.md
  title: ingest/bootstrap/README.md
---

# Purpose

Reads each configured source through a loader, then chunks, embeds, extracts graph entities and replaces changed documents, running as the `sdlc_ingest` database role.

Code: `ingest/bootstrap`

# Responsibilities

- `sdlc-ingest run --all | --source <id> [--dry-run] [--force]`.
- Chunking by Markdown headings, code definitions or line windows.
- PDF text layer per page; opt-in model OCR, cached.
- Graph extraction with structured model output, cleaned before storage.
- Skips unchanged content by hash; removes data of dropped sources.

# Depends on

- [ingest_loaders](ingest_loaders.md)
- [sdlc_db](sdlc_db.md)
- [sdlc_config](sdlc_config.md)
- [sdlc_secrets](sdlc_secrets.md)

# Requirements

- [FR-KNOW-001: Ingest declared sources](../requirements/functional/FR-KNOW-001.md) - Runs the pipeline and tags rows with source and classification.
- [FR-KNOW-003: Knowledge graph queries](../requirements/functional/FR-KNOW-003.md) - Extracts entities and relations per chunk.
- [FR-KNOW-004: PDF ingestion](../requirements/functional/FR-KNOW-004.md) - Reads PDF text and page ranges; OCR only when the source opts in.
- [NFR-REL-004: Repeatable data changes](../requirements/non-functional/NFR-REL-004.md) - Skips unchanged content by hash.
- [NFR-SEC-009: External content is untrusted](../requirements/non-functional/NFR-SEC-009.md) - Cleans extraction output before it is stored.

# Verification

- `tests/ingest/test_chunker.py`
- `tests/ingest/test_graph_extract.py`
- `tests/ingest/test_pdf.py`
- `tests/db/test_pdf_ingest.py`
