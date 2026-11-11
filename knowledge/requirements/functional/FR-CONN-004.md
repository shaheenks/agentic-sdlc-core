---
type: Functional Requirement
title: Service connections for autonomous workflows
description: Autonomous workflows reach Jira, Confluence and Bitbucket through service connections held server-side; initially broad-scoped tokens, later OAuth or system principals.
area: Connections
tags:
- requirement
- functional
- connections
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

The system shall let autonomous workflows read and act on Jira, Confluence and Bitbucket through service connections that are declared in configuration and held only by server-side components.

# Acceptance criteria

- A service connection is declared in configuration: its provider, the workflows that may use it, and a secret reference. The token lives in Secret Manager (locally, the git-ignored secret store), never in config, logs or the database.
- Each autonomous workflow has its own set of service connections; no two workflows share a token, so each can be revoked, rotated and audited on its own.
- Only the MCP backend and the delivery service resolve service connections, and only after the workflow principal's authorization check. No agent, sandbox or user call ever receives one.
- A user's call never falls back to a service connection; that rule (FR-CONN-002) is unchanged.
- The workflow role's argument limits and the Trigger restrict which projects, spaces and repositories a workflow may read or change, whatever the token itself allows.
- Every use is audited as `tool_call` or `delivery`, with credential kind `service`, the connection id and the outcome.
- A service connection can be rotated or revoked without a deploy, and the next call uses the new state.

# Notes

Initial phases (design D11): broad-scoped Jira, Confluence and Bitbucket tokens. OAuth apps or system-principal logins per provider replace them later, without changing this requirement. One set of tokens per workflow, decided 2026-11-11 (design D12).
