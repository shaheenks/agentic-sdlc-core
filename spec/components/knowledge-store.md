---
type: Component
title: Knowledge Store
description: Stores chunks, embeddings and the knowledge graph and answers semantic, keyword and graph queries, filtered to what the caller may read.
tags: [component, knowledge, data]
status: draft
x-layer: knowledge
x-depends-on: [/components/access-policy]
x-satisfies: [/requirements/functional/FR-AUTHZ-004, /requirements/functional/FR-KNOW-001, /requirements/functional/FR-KNOW-002, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-ARCH-004]
---

# Purpose

The knowledge graph backend's store. Only [Knowledge Search](knowledge-search.md) reads it and only the [Ingest Pipeline](ingest-pipeline.md) writes it; the MCP server never touches it. It is part of the isolated knowledge services, not the deferred operations database ([DEC-0003](../decisions/DEC-0003.md)).

The retrieval side of knowledge. Filtering happens in the store itself, so a tool bug cannot leak
rows a user may not read.

# Responsibilities

- Store chunks with embeddings, entities and edges, each tagged with source and classification.
- Answer vector, keyword and hybrid search, and graph traversal queries.
- Hold every record with its `source_id` and classification, so every query can be filtered to the caller's
  readable sources and classification ceiling. With JSONL files, [Knowledge Search](knowledge-search.md) applies
  the filter while reading, before ranking; with PostgreSQL the store enforces it (row-level security).

# Out of scope

- Writing knowledge: only the [Ingest Pipeline](ingest-pipeline.md) writes.

# Interfaces

- Provides: `search(query, scope)`, `graph_query(query, scope)`.
- Consumes: the data scope from the [Access Policy](access-policy.md) decision, passed with each query.

# Depends on

- [Access Policy](access-policy.md)

# Owns

- Chunks, embeddings, entities, edges.

# Requirements

- [FR-AUTHZ-004: Data scope](../requirements/functional/FR-AUTHZ-004.md)
- [FR-KNOW-001: Ingest declared sources](../requirements/functional/FR-KNOW-001.md)
- [FR-KNOW-002: Knowledge search](../requirements/functional/FR-KNOW-002.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-ARCH-004: Knowledge backend isolated](../requirements/non-functional/NFR-ARCH-004.md)

# Realisation

- First version: JSONL files in a local directory set by `KNOWLEDGE_PATH`: chunks with their embeddings,
  entities and edges, one record per line, each with `source_id` and classification. The ingest pipeline writes
  them, and the directory is built into the Knowledge Search image, which reads it at start-up; vector search
  is done in memory. New or changed knowledge reaches search by re-running ingest, rebuilding the image and
  deploying it.
- Next upgrade: PostgreSQL with pgvector, the graph as edge tables and row-level security for the filter; zone
  redundancy for production ([NFR-REL-002](../requirements/non-functional/NFR-REL-002.md)) comes with it.
