---
type: Functional Requirement
title: "Ingest declared sources"
description: "Knowledge sources declared in configuration are ingested and kept fresh."
tags: [requirement, knowledge]
status: draft
x-area: KNOW
x-priority: must
x-implementation: built
---

# Statement

The system shall ingest every knowledge source declared in configuration, tag each record with its source and classification, and keep it in step with the source.

# Acceptance criteria

- Each source is declared with kind, location, classification and access.
- No record is stored without a source ID and classification.
- Re-ingest processes changed content only and removes records whose content is gone.
- Ingest runs with one service identity; every record carries the `source_id` of its source, and the teams that may read each source are declared in configuration, so results are filtered by `source_id`.
- A private `git` source on GitHub, Bitbucket Cloud or Bitbucket Data Center is read with its token signing in as
  the source declares (`credential_scheme`, `credential_username`) or as its host expects by default ([DEC-0014](../../decisions/DEC-0014.md)).

# Notes

For now the knowledge store is JSONL files built into the knowledge search image, so keeping it in step with a source means re-running ingest and deploying a new image.
