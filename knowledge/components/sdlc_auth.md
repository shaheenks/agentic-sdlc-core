---
type: Component
title: sdlc_auth
description: 'Identity: Entra and Google token verification, the principal, Google Groups lookup and user-token passthrough for agents.'
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
- Membership from the `roles` claim only; a `groups` claim is ignored (CH-0011).
- GCP stack (CH-0021): `sdlc_auth.google`: `GoogleTokenVerifier` (issuer `https://accounts.google.com`, our
  OAuth client IDs as audience, `email_verified`, allowed `hd`; user = `sub`), `principal_from_google_claims`,
  `google_verifier_from_env` (`SDLC_OAUTH_CLIENT_IDS`, `SDLC_ALLOWED_DOMAINS`) and `GoogleAdapter` (the
  `sdlc_mcp` identity adapter: `group:<email>` memberships, `users.yaml` by verified email).
- `sdlc_auth.groups`: `CloudIdentityGroups` (direct mode for Cloud Identity Free, transitive for Premium; TTL
  cache per user; failures are failed closed and not cached: in direct mode a failed group gives no roles
  from that group only and the warning names it (CH-0026), in transitive mode an error gives no groups;
  `check` resolves each configured group for `sdlc-config check-groups`) and `StaticGroups` for tests.
- `get_user_token` and `agent_header_provider` for ADK agents; with `SDLC_MCP_IAM_AUDIENCE`
  the provider also sends the agent's Google ID token in `X-Serverless-Authorization` for
  Cloud Run IAM (CH-0014), never in `Authorization`.
- `verifier_from_env`: the Entra verifier agents use (shared by `sdlc_web` and the runtime app).

# Depends on

- [sdlc_config](sdlc_config.md)

# Requirements

- [FR-IDN-001: Sign-in with Entra ID](../requirements/functional/FR-IDN-001.md) - Verifies Entra tokens for the MCP server.
- [FR-IDN-002: Membership from app roles and direct members](../requirements/functional/FR-IDN-002.md) - Reads app roles from the token; ignores a `groups` claim.
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
