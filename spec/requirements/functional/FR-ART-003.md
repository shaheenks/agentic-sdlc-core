---
type: Functional Requirement
title: "Artifact retention of 7 days"
description: "Artifacts live in a dedicated bucket and are deleted 7 days after they are created."
tags: [requirement, artifacts]
status: draft
x-area: ART
x-priority: must
x-implementation: planned
---

# Statement

The system shall store artifacts in a dedicated Cloud Storage bucket per environment, whose lifecycle policy
deletes each artifact 7 days after it is created.

# Acceptance criteria

- The bucket's lifecycle rule deletes objects 7 days after creation; no other component deletes them early except
  the owner's own delete.
- Surfaces show each artifact's expiry date.
- Within those 7 days, saving a revision keeps earlier versions readable.
- Size and type limits are enforced when an artifact is stored.
- The lifecycle rule applies to the `artifacts/` prefix only; connection secrets kept in the same bucket ([DEC-0006](../../decisions/DEC-0006.md)) are not deleted by it.
- Only the two MCP servers mount and use the bucket, each limited by IAM conditions to its own prefixes (user_agent_mcp: `artifacts/users/`, `secrets/users/`; event_agent_mcp: `artifacts/system/`); users reach artifacts through them.
