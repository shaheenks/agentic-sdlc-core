---
type: Component
title: scripts
description: 'Operator scripts: Entra provisioning, GCP deployment steps, manual identity and A2A checks, sample PDF generation, and the knowledge-bundle tool.'
area: Delivery
tags:
- component
- delivery
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../scripts
satisfies:
- /requirements/functional/FR-CFG-003
- /requirements/functional/FR-IDN-002
- /requirements/non-functional/NFR-MAINT-005
- /requirements/non-functional/NFR-PRIV-003
verified_by:
- tests/knowledge
---

# Purpose

Hands-on tooling run by a person, not by services.

Code: `scripts`

# Responsibilities

- `entra_setup.ps1`: idempotent Entra provisioning including app roles.
- `gcp_deploy.ps1`: state, base, config, images, plan, apply, db, ingest, urls.
- `mcp_whoami.py`, `a2a_client.py`, `make_sample_pdfs.py`, `okf_bundle.py`.

# Depends on

- [sdlc_config](sdlc_config.md)
- [infra_gcp](infra_gcp.md)

# Requirements

- [FR-CFG-003: Immutable config bundles with rollback](../requirements/functional/FR-CFG-003.md) - Publishes and rolls back config bundles on GCP.
- [FR-IDN-002: Membership from app roles and direct members](../requirements/functional/FR-IDN-002.md) - Defines the Entra app roles the configuration references.
- [NFR-MAINT-005: The specification is traced and checked](../requirements/non-functional/NFR-MAINT-005.md) - `okf_bundle.py`: lint, generated indexes and traceability matrix, drift hints.
- [NFR-PRIV-003: Tenant data stays out of the repository](../requirements/non-functional/NFR-PRIV-003.md) - Takes tenant user names on the command line, never from the repository.

# Verification

- `tests/knowledge` (`okf_bundle.py`; the PowerShell scripts stay manual)
