---
type: Functional Requirement
title: Event enrichment
description: Events are enriched with the workflow's agent context and real-time context before an agent runs.
area: Workflows
tags:
- requirement
- functional
- workflows
status: draft
priority: must
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

The system shall enrich each accepted event with the agent context of its workflow and the real-time context the workflow needs, before an agent processes it.

# Acceptance criteria

- Enrichment resolves the Workflow and team from the matched Trigger, never from the payload.
- Agent context (team instructions, skills, knowledge references) and real-time context (PR diff, pipeline log, alert, log lines) are fetched through the MCP server as the workflow principal.
- Enrichment runs no model and holds no write credential.
- Fetched content is marked as untrusted data in the enriched event.
