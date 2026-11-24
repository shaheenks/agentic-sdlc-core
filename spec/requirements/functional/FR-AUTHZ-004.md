---
type: Functional Requirement
title: "Data scope"
description: "Knowledge reads are limited to the sources a user may read, up to their classification ceiling."
tags: [requirement, authorization]
status: draft
x-area: AUTHZ
x-priority: must
x-implementation: planned
---

# Statement

The system shall limit every knowledge read to the sources the user may read and to the user's classification ceiling for each source.

# Acceptance criteria

- A search never returns a record from a source the user cannot read, even when the calling tool asks for more.
- The MCP server computes the scope from the verified caller's grants and passes it to the knowledge search service as a filter attribute; the search service refuses a query without one.
- The knowledge search service applies the scope before any result is ranked or returned, so a defect in a tool
  cannot widen it. With PostgreSQL, the next upgrade, the data store itself enforces it.
