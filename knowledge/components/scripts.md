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
- /requirements/non-functional/NFR-SEC-015
verified_by:
- tests/infra/test_gcp_stack_scripts.py
- tests/infra/test_image_tags.py
- tests/knowledge
---

# Purpose

Hands-on tooling run by a person, not by services.

Code: `scripts`

# Responsibilities

- `entra_setup.ps1`: idempotent Entra provisioning including app roles.
- `gcp_deploy.ps1`: state, base, config, images, plan, apply, db, ingest, urls.
- CH-0024: `build_tag.py` holds the image list (Terraform key, registry name, Dockerfile) and tags each image
  `src-<12 hex>`, a SHA-256 of `git ls-tree` over its committed inputs (Dockerfile, `.dockerignore`, every
  `COPY`/`ADD` source; a source missing from the commit fails). `gcp_deploy.ps1` reads it: `images` skips tags
  already in the registry (`-Rebuild` builds all), `plan` stops if one is not pushed and passes
  `TF_VAR_image_tags`; `-ImageTag` sets one tag for all (older tags, rollback).
- `deploy_agent_runtime.py` (CH-0014): stages the user agent as a source package and creates or
  updates its Agent Runtime engine with Agent Identity; run by the user.
- `agent_runtime_query.py` (CH-0014): asks the agent on Agent Runtime a question with a user's token and
  prints each event with its arrival time (streaming check), then the user's conversations.
- `mcp_whoami.py`, `a2a_client.py`, `make_sample_pdfs.py`, `okf_bundle.py`.
- CH-0022: `deploy_agent_runtime.py --idp google` (default; `entra` = rollback) sets the Google settings
  (client IDs from .env, domains from config); `google_id_token.py` (installed-app sign-in with PKCE for a
  Desktop client) behind `agent_runtime_query.py` / `mcp_whoami.py --idp google`; `gcp_deploy.ps1` builds
  `core-mcp-gcp` and passes the client IDs.

# Depends on

- [sdlc_config](sdlc_config.md)
- [infra_gcp](infra_gcp.md)

# Requirements

- [FR-CFG-003: Immutable config bundles with rollback](../requirements/functional/FR-CFG-003.md) - Publishes and rolls back config bundles on GCP.
- [FR-IDN-002: Membership from app roles and direct members](../requirements/functional/FR-IDN-002.md) - Defines the Entra app roles the configuration references.
- [NFR-MAINT-005: The specification is traced and checked](../requirements/non-functional/NFR-MAINT-005.md) - `okf_bundle.py`: lint, generated indexes and traceability matrix, drift hints.
- [NFR-PRIV-003: Tenant data stays out of the repository](../requirements/non-functional/NFR-PRIV-003.md) - Takes tenant user names on the command line, never from the repository.
- [NFR-SEC-015: Layered access control on Google Cloud](../requirements/non-functional/NFR-SEC-015.md) - `deploy_agent_runtime.py` attaches the engine to the Agent Gateway.

# Verification

- `tests/infra/test_gcp_stack_scripts.py`
- `tests/knowledge` (`okf_bundle.py`; the PowerShell scripts stay manual)
