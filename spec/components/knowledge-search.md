---
type: Component
title: "Knowledge Search"
description: "A separately hosted search service over the knowledge graph backend: semantic, keyword, hybrid and graph queries, filtered by the data-scope attribute the MCP server sends."
tags: [component, knowledge]
status: draft
x-layer: knowledge
x-folder: knowledge_search/
x-depends-on: [/components/knowledge-store, /components/observability]
x-satisfies: [/requirements/functional/FR-AUTHZ-004, /requirements/functional/FR-KNOW-002, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-ARCH-002, /requirements/non-functional/NFR-ARCH-003, /requirements/non-functional/NFR-ARCH-004, /requirements/non-functional/NFR-OPS-002, /requirements/functional/FR-AGT-005, /requirements/functional/FR-KNOW-004]
---

# Purpose

The read side of the knowledge backend, isolated from the MCP servers ([NFR-ARCH-004](../requirements/non-functional/NFR-ARCH-004.md)). The MCP servers proxy agents' knowledge requests here with a filter attribute; the user's token stays with the MCP server.

# Responsibilities

- Accept calls only from the MCP servers' service accounts (Cloud Run invoker IAM and a Google-signed ID token
  with this service as audience).
- Require a filter attribute on every query: the readable source IDs and the classification ceiling per source
  that the MCP server computed for the caller. Refuse a query without one.
- Answer vector, keyword, hybrid and graph queries against the [Knowledge Store](knowledge-store.md), embedding
  queries on Vertex AI, with the filter applied before any result is ranked or returned.
- Return results with their source ID and a link or path to the original.

# Out of scope

- Writing knowledge: the [Ingest Pipeline](ingest-pipeline.md).
- Deciding what a caller may read: the MCP servers, through the [Access Policy](access-policy.md).
- Verifying user tokens: the MCP servers.

# Interfaces

- Provides: an HTTP search API (`search`, `graph_query`, each with a filter attribute) for user_agent_mcp and event_agent_mcp.
- Consumes: the knowledge store, embeddings; URLs from environment variables.

# Depends on

- [Knowledge Store](knowledge-store.md)
- [Observability](observability.md)

# Owns

- Nothing durable.

# Requirements

- [FR-AUTHZ-004: Data scope](../requirements/functional/FR-AUTHZ-004.md)
- [FR-KNOW-002: Knowledge search](../requirements/functional/FR-KNOW-002.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-ARCH-002: Hostnames and service URLs are configuration](../requirements/non-functional/NFR-ARCH-002.md)
- [NFR-ARCH-003: Self-contained components](../requirements/non-functional/NFR-ARCH-003.md)
- [NFR-ARCH-004: Knowledge backend isolated](../requirements/non-functional/NFR-ARCH-004.md)
- [NFR-OPS-002: Local Docker Compose environment](../requirements/non-functional/NFR-OPS-002.md)
- [FR-AGT-005: Ad-hoc knowledge search and brainstorm chat](../requirements/functional/FR-AGT-005.md)
- [FR-KNOW-004: Knowledge scope: broad in chat, team in workflows](../requirements/functional/FR-KNOW-004.md)

# Realisation

- The knowledge JSONL directory is built into the image and loaded at start-up ([Knowledge Store](knowledge-store.md)); the image is read-only, so the service writes nothing.
- Folder `knowledge_search/`, self-contained; a Cloud Run service in europe-west3 with internal-only ingress,
  reached by the two MCP servers through their VPC egress, with Cloud Run invoker granted to their service
  accounts alone.
