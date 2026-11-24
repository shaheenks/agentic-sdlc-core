---
type: Functional Requirement
title: "Knowledge search"
description: "Agents search knowledge by meaning, keyword and graph through the MCP server, which proxies to the knowledge search service."
tags: [requirement, knowledge]
status: draft
x-area: KNOW
x-priority: must
x-implementation: built
---

# Statement

The system shall answer semantic, keyword, hybrid and graph queries over ingested knowledge from a separately
hosted knowledge search service, reached through the MCP server, citing the source location of each result.

# Acceptance criteria

- Every result carries its source ID and a link or path to the original.
- Results are scoped per [FR-AUTHZ-004](FR-AUTHZ-004.md), by the search service.
- The MCP server proxies the request with a filter attribute that carries the caller's data scope; the user's token stays with the MCP server ([NFR-ARCH-004](../non-functional/NFR-ARCH-004.md)).
