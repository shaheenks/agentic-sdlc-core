---
type: Component
title: sdlc_auth
description: 'Entra ID identity: token verification, the principal, group resolution and user-token passthrough for agents.'
area: Libraries
tags:
- component
- libraries
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../libs/sdlc_auth
satisfies:
- /requirements/functional/FR-IDN-001
- /requirements/functional/FR-IDN-002
- /requirements/functional/FR-IDN-004
- /requirements/non-functional/NFR-AUD-002
- /requirements/non-functional/NFR-PORT-001
- /requirements/non-functional/NFR-REL-002
- /requirements/non-functional/NFR-SEC-003
- /requirements/non-functional/NFR-SEC-004
- /requirements/non-functional/NFR-SEC-006
verified_by:
- tests/auth
- tests/web/test_token_passthrough.py
- tests/mcp/test_blocklist.py
sources:
- id: readme
  resource: ../../libs/sdlc_auth/README.md
  title: libs/sdlc_auth/README.md
---

# Purpose

Turns a validated Entra token into a `Principal`, and gives agents the user's token to forward.

Code: `libs/sdlc_auth`

# Responsibilities

- `EntraTokenVerifier`: v2 issuer, audience, scope, tenant, signature, expiry; block-list check.
- `Principal` from validated claims, including app roles.
- Group resolution; overage yields no groups (Graph fallback present but off).
- `get_user_token` and `agent_header_provider` for ADK agents.

# Depends on

- [sdlc_config](sdlc_config.md)

# Requirements

- [FR-IDN-001: Sign-in with Entra ID](../requirements/functional/FR-IDN-001.md) - Verifies Entra tokens for the MCP server.
- [FR-IDN-002: Membership from groups, app roles and direct members](../requirements/functional/FR-IDN-002.md) - Reads groups and app roles from the token; overage yields no groups.
- [FR-IDN-004: Revocation of access](../requirements/functional/FR-IDN-004.md) - Checks the block list during token verification.
- [NFR-AUD-002: Records can be correlated](../requirements/non-functional/NFR-AUD-002.md) - Sends the conversation id header that becomes `agent_session_id`.
- [NFR-PORT-001: Tenant-agnostic identity](../requirements/non-functional/NFR-PORT-001.md) - Takes tenant, client and authority host from configuration.
- [NFR-REL-002: Stable MCP sessions](../requirements/non-functional/NFR-REL-002.md) - Keys the MCP session on user token and conversation only.
- [NFR-SEC-003: Strict token validation](../requirements/non-functional/NFR-SEC-003.md) - Implements the token checks.
- [NFR-SEC-004: Fail closed](../requirements/non-functional/NFR-SEC-004.md) - Fails closed when the signing keys cannot be reached.
- [NFR-SEC-006: Calls are made as the user](../requirements/non-functional/NFR-SEC-006.md) - Provides the user-token passthrough agents use.

# Verification

- `tests/auth`
- `tests/web/test_token_passthrough.py`
- `tests/mcp/test_blocklist.py`
