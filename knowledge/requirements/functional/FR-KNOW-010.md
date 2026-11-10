---
type: Functional Requirement
title: Diverse document formats
description: Office documents, API specifications and structured data are ingested with format-aware chunking.
area: Knowledge
tags:
- requirement
- functional
- knowledge
status: draft
priority: could
implementation: planned
sources:
- id: design
  resource: ../../../docs/designs/workflow-platform.md
  title: Workflow platform target design
- id: change
  resource: ../../changes/CH-0008.md
  title: CH-0008 Workflow platform design baseline
---

# Statement

The system shall ingest Office documents, API specifications and tabular data with chunking that keeps their structure.

# Acceptance criteria

- Word, PowerPoint and Excel files, including those from SharePoint, are loaded with their headings, slides or sheets kept as citation units.
- OpenAPI specifications are chunked per operation and per schema.
- Tables keep their header with every chunk.

# Notes

SharePoint and Office documents are planned in version-03 P8.
