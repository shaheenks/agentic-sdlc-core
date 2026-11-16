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
- /requirements/non-functional/NFR-SEC-015
verified_by:
- tests/infra/test_terraform.py
- tests/infra/test_image_tags.py
---

# Purpose

Provisions the cloud environment. Applied by the user through `scripts/gcp_deploy.ps1`.

Code: `infra/gcp`

# Responsibilities

- Cloud Run: `sdlc-app` (oauth2-proxy, agent and chat) and `sdlc-mcp`; jobs for database setup, ingest and reconcile.
- Cloud SQL with pgvector; GCS buckets for config, artifacts and sources; Secret Manager.
- Cloud Scheduler; Agent Engine sessions; per-service accounts and IAM.
- CH-0022: `sdlc-mcp-native` runs `core-mcp-gcp` as `sdlc-<env>-mcp-gcp` (the same grants as `mcp`) with
  `SDLC_OAUTH_CLIENT_IDS` (`var.google_oauth_client_ids`) instead of `ENTRA_*`; `cloudidentity.googleapis.com`
  with `native_enabled`; the agent's gateway egress `google-signing-keys` replaces `entra-signing-keys`; output
  `mcp_gcp_service_account` (for Groups Reader).
- CH-0016: `ui_native.tf`: `sdlc-ui-native` (the `ui-copilotkit` image with `native-entry.mjs`) behind direct
  IAP for `var.iap_access_group`, IAP's service agent as its only invoker; its own service account with Agent
  Runtime query and invoker on `sdlc-mcp-native`; the Web client secret and a generated cookie key in Secret
  Manager; the engine from `agent_runtime_principal`, the domains from `platform.yaml`.
- CH-0024: `var.image_tags` (exactly `mcp`, `mcp_gcp`, `agent`, `ingest`, `ui`) replaces `image_tag`, one
  tag per image in `local.images`, so a service rolls out only when its own image changed; `sdlc-ui-native`
  pins no `launch_stage` (Cloud Run reports direct IAP as GA).

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
- [NFR-SEC-010: Least-privilege runtime](../requirements/non-functional/NFR-SEC-010.md) - One service account per workload with scoped IAM; `sdlc-mcp-native` has invoker IAM on (CH-0013).
- [NFR-SEC-015: Layered access control on Google Cloud](../requirements/non-functional/NFR-SEC-015.md) - Agent Gateway (egress), the registry entry for `sdlc-mcp-native`, the IAP extension and policy, and the agent's tool-scoped `roles/iap.egressor` grant; the agent's other destinations (Entra keys, Gemini, sessions) as registered endpoints with their own grants (CH-0018).

# Verification

- `tests/infra/test_terraform.py`; CI also runs `terraform validate`.
