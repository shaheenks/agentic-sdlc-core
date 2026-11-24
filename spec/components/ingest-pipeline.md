---
type: Component
title: Ingest Pipeline
description: Reads declared knowledge sources, chunks, embeds and extracts a knowledge graph, tagging every record with its source and classification.
tags: [component, knowledge]
status: draft
x-layer: knowledge
x-folder: knowledge_ingest/
x-depends-on: [/components/configuration-registry, /components/connectors, /components/knowledge-store, /components/observability]
x-satisfies: [/requirements/functional/FR-KNOW-001, /requirements/functional/FR-KNOW-003, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-ARCH-002, /requirements/non-functional/NFR-ARCH-003, /requirements/non-functional/NFR-ARCH-004, /requirements/non-functional/NFR-OPS-002]
---

# Purpose

Gives workflows a grounded view of a team's systems: code, designs, tickets, documentation.

# Responsibilities

- Ingest each source declared in configuration (repositories at a pinned commit or tracked branch, buckets, wikis, issue trackers) on schedule or on change.
- Chunk, embed (on Vertex AI) and extract entities and relations into the [Knowledge Store](knowledge-store.md).
- Tag every record with its source ID and classification; never write untagged data.
- Ingest incrementally and remove records whose source content is gone.
- Report each ingest run's status per source.

# Out of scope

- Serving queries: the [Knowledge Store](knowledge-store.md).

# Interfaces

- Provides: ingest jobs, per-source status.
- Consumes: source declarations, connector reads, embeddings.

# Depends on

- [Configuration Registry](configuration-registry.md)
- [Connectors](connectors.md)
- [Knowledge Store](knowledge-store.md)
- [Observability](observability.md)

# Owns

- Ingest run history and per-source checkpoints.

# Requirements

- [FR-KNOW-001: Ingest declared sources](../requirements/functional/FR-KNOW-001.md)
- [FR-KNOW-003: Ingest status](../requirements/functional/FR-KNOW-003.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-ARCH-002: Hostnames and service URLs are configuration](../requirements/non-functional/NFR-ARCH-002.md)
- [NFR-ARCH-003: Self-contained components](../requirements/non-functional/NFR-ARCH-003.md)
- [NFR-ARCH-004: Knowledge backend isolated](../requirements/non-functional/NFR-ARCH-004.md)
- [NFR-OPS-002: Local Docker Compose environment](../requirements/non-functional/NFR-OPS-002.md)

# Realisation

- Folder `knowledge_ingest/`, self-contained, separate from the MCP servers and from Knowledge Search; the only
  writer of the Knowledge Store. For now it runs as a step of the build pipeline, before the Knowledge Search image is built, and writes the JSONL
  directory into that image's build input; a refresh is a new ingest run followed by a new image.
- Runs with one service identity, a dedicated service account, for every source. Every record carries the `source_id` of its source; the teams that may read a source are declared in configuration, and Knowledge Search filters on `source_id` ([FR-AUTHZ-004](../requirements/functional/FR-AUTHZ-004.md)).
