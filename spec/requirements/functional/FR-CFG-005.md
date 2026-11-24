---
type: Functional Requirement
title: "Configuration bucket"
description: "The active configuration is published to a dedicated Cloud Storage bucket that the MCP server reads while answering requests."
tags: [requirement, configuration]
status: draft
x-area: CFG
x-priority: must
x-implementation: planned
---

# Statement

The system shall publish each validated configuration bundle to a dedicated Cloud Storage bucket per
environment, and the MCP server shall resolve each request against the active bundle in that bucket.

# Acceptance criteria

- The bucket holds the versioned bundles and an object naming the active version; object versioning is on.
- Only the publishing pipeline can write to it; only platform service accounts can read it.
- user_agent_mcp reads the active bundle while answering requests, caching it by object generation, so a newly
  activated version takes effect within a minute without a restart.
- If the bucket cannot be read and no verified bundle is cached, requests are refused.
