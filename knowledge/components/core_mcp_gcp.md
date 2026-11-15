---
type: Component
title: core_mcp_gcp
description: 'The MCP server of the GCP stack: sdlc_mcp with the Google ID token verifier and the Google Groups identity adapter.'
area: Services
tags:
- component
- services
status: draft
resource: ../../mcp_servers/core_mcp_gcp
satisfies:
- /requirements/functional/FR-ART-001
- /requirements/non-functional/NFR-SEC-001
- /requirements/non-functional/NFR-SEC-004
- /requirements/non-functional/NFR-SEC-010
verified_by:
- tests/mcp/test_core_mcp_gcp.py
sources:
- id: readme
  resource: ../../mcp_servers/core_mcp_gcp/README.md
  title: mcp_servers/core_mcp_gcp/README.md
- id: change
  resource: ../changes/CH-0022.md
  title: CH-0022 core_mcp_gcp and the GCP stack on Google identity
---

# Purpose

The GCP stack's MCP server (CH-0022), behind `sdlc-mcp-native`. Like [core_mcp](core_mcp.md) it is only an entry
point: the server is the [sdlc_mcp](sdlc_mcp.md) library, and the Google verifier and adapter are
[sdlc_auth](sdlc_auth.md)'s (CH-0021).

Code: `mcp_servers/core_mcp_gcp`

# Responsibilities

- `server.py`: `build_auth` (Google ID token verifier: our OAuth client IDs from `SDLC_OAUTH_CLIENT_IDS`, the
  allowed domains from `platform.yaml` `identity.google`, the block list by `sub`; RFC 9728 metadata naming
  Google), `build_identity` (the Google adapter with `CloudIdentityGroups` in the configured lookup mode, as the
  service's own account) and the `sdlc-core-mcp-gcp` entry point. Missing settings stop startup.
- Image `core-mcp-gcp`; on GCP it runs as `sdlc-<env>-mcp-gcp`, the only account with Groups Reader.

# Depends on

- [sdlc_mcp](sdlc_mcp.md)
- [sdlc_auth](sdlc_auth.md)
- [sdlc_config](sdlc_config.md)

# Requirements

- [FR-ART-001: Save and manage artifacts](../requirements/functional/FR-ART-001.md) - The owner is the Google `sub` on this stack.
- [NFR-SEC-001: Single enforcement point](../requirements/non-functional/NFR-SEC-001.md) - The deployed enforcement point of the GCP stack (the checks are `sdlc_mcp`).
- [NFR-SEC-004: Fail closed](../requirements/non-functional/NFR-SEC-004.md) - Refuses to start without client IDs or `identity.google`; a failed group lookup gives no groups.
- [NFR-SEC-010: Least-privilege runtime](../requirements/non-functional/NFR-SEC-010.md) - Its own service account, the only caller of the Cloud Identity Groups API.

# Verification

- `tests/mcp/test_core_mcp_gcp.py`
