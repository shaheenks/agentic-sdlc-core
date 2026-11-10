---
type: Non-Functional Requirement
title: MCP backends can be segregated per workflow
description: A workflow can get its own MCP backend that serves only its tools and holds only its credentials, under the same config and policy.
area: Security
tags:
- requirement
- non-functional
- security
status: draft
priority: should
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

The system shall support running a dedicated MCP backend for a workflow, or a workflow class, that serves only the tools assigned to it and holds only the credentials those tools need, without changing how access is declared or enforced.

# Acceptance criteria

- `tools.yaml` assigns each tool to a server. A backend serves only its assigned tools, and a call to any other tool is refused as unknown.
- A backend holds only the secrets and service connections of its own tools.
- A backend can have its own Entra app registration (token audience), so a token issued for one backend is refused by another.
- Every backend uses the same `ConfigStore`, policy engine and audit format. No backend has authorization code of its own.
- A workflow's agent is configured with its own backend only. Moving a workflow to a dedicated backend is a configuration and deployment change, not a code change in the agent.
- Until a split is needed, the single `core_mcp` serves every tool.

# Notes

Decided 2026-11-11 (design D10): one MCP server and API backend today; a dedicated backend is added whenever least privilege or identity separation requires it.
