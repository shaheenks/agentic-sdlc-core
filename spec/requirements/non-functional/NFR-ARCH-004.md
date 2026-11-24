---
type: Non-Functional Requirement
title: "Knowledge backend isolated"
description: "Knowledge ingestion and search run as their own services; the MCP server only proxies to them."
tags: [requirement, architecture]
status: draft
x-area: ARCH
x-priority: must
x-implementation: built
---

# Statement

The system shall run knowledge ingestion and knowledge search as services of their own, separate from the MCP
server, which only proxies knowledge requests to the search service.

# Acceptance criteria

- The MCP server holds no credentials for the knowledge store and runs no knowledge queries itself.
- The MCP server keeps the user's token. It sends each proxied request with a filter attribute (readable source
  IDs and classification ceiling per source) that it computed from the verified caller's grants.
- The search service accepts calls only from the MCP servers' service accounts, refuses a query without a
  filter attribute, and applies the filter before any result is ranked or returned.
- Ingestion and search are deployed, scaled and released independently of the MCP server.
