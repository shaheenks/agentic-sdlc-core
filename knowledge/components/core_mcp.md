---
type: Component
title: core_mcp
description: 'The MCP server of the Entra stack: sdlc_mcp with the Entra token verifier and identity adapter.'
area: Services
tags:
- component
- services
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../mcp_servers/core_mcp
satisfies:
- /requirements/functional/FR-IDN-001
- /requirements/functional/FR-SURF-003
- /requirements/non-functional/NFR-SEC-001
- /requirements/non-functional/NFR-SEC-004
verified_by:
- tests/mcp
- tests/mcp/test_server_library.py
sources:
- id: readme
  resource: ../../mcp_servers/core_mcp/README.md
  title: mcp_servers/core_mcp/README.md
---

# Purpose

The Entra stack's MCP server. The server itself (tools, policy middleware, audit, artifacts and connections
APIs) is the [sdlc_mcp](sdlc_mcp.md) library; this component supplies the Entra parts only (CH-0020).

Code: `mcp_servers/core_mcp`

# Responsibilities

- `server.py`: the Entra token verifier with OAuth protected-resource metadata (RFC 9728) and the block list,
  the `sdlc-core-mcp` entry point, and `build_server` / `build_http_app` with the Entra adapter.
- `entra.py`: `EntraAdapter`: the user is the `oid`; memberships are the token's app roles; `users.yaml` is
  matched on `oid`; the `whoami` view; why a rejected Entra token was refused (expired, wrong tenant, issuer,
  audience, scope, blocked).

# Depends on

- [sdlc_mcp](sdlc_mcp.md)
- [sdlc_auth](sdlc_auth.md)
- [sdlc_config](sdlc_config.md)

# Requirements

- [FR-IDN-001: Sign-in with Entra ID](../requirements/functional/FR-IDN-001.md) - Verifies Entra tokens (answers 401 without one) and classifies rejected tokens for `auth_failure`.
- [FR-SURF-003: Direct MCP clients](../requirements/functional/FR-SURF-003.md) - Streamable HTTP endpoint for direct MCP clients.
- [NFR-SEC-001: Single enforcement point](../requirements/non-functional/NFR-SEC-001.md) - The deployed enforcement point of the Entra stack (the checks are `sdlc_mcp`).
- [NFR-SEC-004: Fail closed](../requirements/non-functional/NFR-SEC-004.md) - Refuses to start without valid config and Entra IDs.

# Verification

- `tests/mcp`
- `tests/mcp/test_server_library.py`
