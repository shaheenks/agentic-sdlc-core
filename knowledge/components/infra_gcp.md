---
type: Component
title: infra_gcp
description: 'Terraform for the GCP environment: Cloud Run services and jobs, Cloud SQL, storage, secrets, schedules and IAM.'
area: Delivery
tags:
- component
- delivery
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../infra/gcp
satisfies:
- /requirements/functional/FR-CFG-003
- /requirements/functional/FR-IDN-001
- /requirements/functional/FR-IDN-004
- /requirements/functional/FR-KNOW-005
- /requirements/non-functional/NFR-OBS-001
- /requirements/non-functional/NFR-PORT-003
- /requirements/non-functional/NFR-PRIV-004
- /requirements/non-functional/NFR-SEC-007
- /requirements/non-functional/NFR-SEC-010
verified_by:
- tests/infra/test_terraform.py
---

# Purpose

Provisions the cloud environment. Applied by the user through `scripts/gcp_deploy.ps1`.

Code: `infra/gcp`

# Responsibilities

- Cloud Run: `sdlc-app` (oauth2-proxy, agent and chat) and `sdlc-mcp`; jobs for database setup, ingest and reconcile.
- Cloud SQL with pgvector; GCS buckets for config, artifacts and sources; Secret Manager.
- Cloud Scheduler; Agent Engine sessions; per-service accounts and IAM.

# Depends on

- [core_mcp](core_mcp.md)
- [sdlc_web](sdlc_web.md)
- [copilotkit](copilotkit.md)
- [ingest_bootstrap](ingest_bootstrap.md)

# Requirements

- [FR-CFG-003: Immutable config bundles with rollback](../requirements/functional/FR-CFG-003.md) - Config store bucket the services read bundles from.
- [FR-IDN-001: Sign-in with Entra ID](../requirements/functional/FR-IDN-001.md) - Runs oauth2-proxy in front of the app.
- [FR-IDN-004: Revocation of access](../requirements/functional/FR-IDN-004.md) - Scheduled reconcile job.
- [FR-KNOW-005: Scheduled ingest](../requirements/functional/FR-KNOW-005.md) - Scheduler that starts the ingest job.
- [NFR-OBS-001: End-to-end tracing](../requirements/non-functional/NFR-OBS-001.md) - Cloud Trace export.
- [NFR-PORT-003: Local and cloud parity](../requirements/non-functional/NFR-PORT-003.md) - Is the cloud deployment of the same components.
- [NFR-PRIV-004: Bounded data retention](../requirements/non-functional/NFR-PRIV-004.md) - Artifact bucket lifecycle.
- [NFR-SEC-007: Secrets handling](../requirements/non-functional/NFR-SEC-007.md) - Secret Manager secrets and their access.
- [NFR-SEC-010: Least-privilege runtime](../requirements/non-functional/NFR-SEC-010.md) - One service account per workload with scoped IAM.

# Verification

- `tests/infra/test_terraform.py`; CI also runs `terraform validate`.
