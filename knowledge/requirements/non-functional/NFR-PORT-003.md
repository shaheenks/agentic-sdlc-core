---
type: Non-Functional Requirement
title: Local and cloud parity
description: The same components run under Docker Compose locally and on GCP.
area: Portability
tags:
- requirement
- non-functional
- portability
status: draft
priority: should
implementation: live
sources:
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: arch
  resource: ../../../docs/ARCHITECTURE.md
  title: System architecture
---

# Statement

The same components shall run locally under Docker Compose and on GCP without code changes.

# Acceptance criteria

- Local: Docker Compose (Postgres, MCP server, agent, oauth2-proxy). Compose is the local twin of each stack: the
  default profile runs the Entra stack, profile `gcp` the GCP stack (Google sign-in, the agent with Google
  identity, `core-mcp-gcp`).
- GCP dev: Cloud Run, Cloud SQL with pgvector, GCS and Secret Manager, provisioned with Terraform.
- `infra/gcp` stays valid when shared code changes.
- GCP-native hosting: the agent runs on Agent Runtime behind the same entry checks as local (`sdlc_agent.runtime_guard`); local compose runs the same agent code in a container.

# Notes

Only the dev environment exists on GCP; staging was dropped for version-03.

Edited by CH-0014: the agent on Agent Runtime (design D17).

Edited by CH-0022: a compose profile per stack.
