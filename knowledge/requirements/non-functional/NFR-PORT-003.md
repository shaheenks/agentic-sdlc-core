---
type: Non-Functional Requirement
title: Local and cloud parity
description: The same components run under Docker Compose locally and on GCP.
area: Portability
tags:
- requirement
- non-functional
- portability
status: stable
priority: should
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:45:18+05:30'
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

- Local: Docker Compose (Postgres, MCP server, agent, oauth2-proxy).
- GCP dev: Cloud Run, Cloud SQL with pgvector, GCS and Secret Manager, provisioned with Terraform.
- `infra/gcp` stays valid when shared code changes.

# Notes

Only the dev environment exists on GCP; staging was dropped for version-03.
