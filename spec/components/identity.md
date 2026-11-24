---
type: Component
title: Identity
description: Authenticates callers against the enterprise identity provider and turns a token into a verified platform identity.
tags: [component, control, security]
status: draft
x-layer: control
x-folder: libs/sdlc_identity/
x-depends-on: [/components/configuration-registry, /components/audit-log]
x-satisfies: [/requirements/functional/FR-SURF-002, /requirements/functional/FR-SURF-003, /requirements/functional/FR-SURF-005, /requirements/functional/FR-IDN-001, /requirements/functional/FR-IDN-002, /requirements/functional/FR-IDN-003, /requirements/functional/FR-IDN-004, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-SEC-002, /requirements/non-functional/NFR-SEC-003, /requirements/non-functional/NFR-SEC-007, /requirements/non-functional/NFR-AUD-001]
---

# Purpose

Answers one question for every request: who is calling? Everything downstream acts as that user.

# Responsibilities

- Verify Google-issued tokens for accounts of the organisation's Cloud Identity account: ID tokens locally against Google's keys, access tokens by introspection, caching each verified token per instance for 300 seconds or until it expires if sooner. Accept only tokens issued to the platform's own OAuth clients ([DEC-0001](../decisions/DEC-0001.md)).
- Map a token to the stable Google account ID and the account's email; group membership comes from the [Directory](directory.md).
- Know each surface by the OAuth client its tokens were issued to (sdlc_ui, Gemini Enterprise, each declared third-party A2A or MCP surface, agents on Agent Runtime) and refuse tokens from undeclared clients.
- Represent the system identity of unattended runs, a dedicated service account, as a distinct non-human identity.
- Apply the block list; a blocked or unverifiable caller is refused (fail closed).
- Obtain delegated tokens so downstream calls are made as the user where the provider supports it.
- Record each authentication failure and its reason in the [Audit Log](audit-log.md), never the token.

# Out of scope

- What the user may do: the [Access Policy](access-policy.md).
- Team membership: the [Directory](directory.md).
- User accounts and sign-in: Cloud Identity, federated to Microsoft Entra ID.

# Interfaces

- Provides: `verify(token) -> Identity`; OAuth protected-resource metadata for clients.
- Consumes: identity-provider keys and metadata; identity settings from the [Configuration Registry](configuration-registry.md).

# Depends on

- [Configuration Registry](configuration-registry.md)
- [Audit Log](audit-log.md)

# Owns

- No user data; caches provider keys only.

# Requirements

- [FR-SURF-002: A2A router](../requirements/functional/FR-SURF-002.md)
- [FR-SURF-003: Gemini Enterprise app](../requirements/functional/FR-SURF-003.md)
- [FR-SURF-005: Third-party AI surfaces over A2A](../requirements/functional/FR-SURF-005.md)
- [FR-IDN-001: Sign-in with Cloud Identity, federated from Entra ID](../requirements/functional/FR-IDN-001.md)
- [FR-IDN-002: Act as the user end to end](../requirements/functional/FR-IDN-002.md)
- [FR-IDN-003: Block list](../requirements/functional/FR-IDN-003.md)
- [FR-IDN-004: System identity for unattended runs](../requirements/functional/FR-IDN-004.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-SEC-002: Deny by default, fail closed](../requirements/non-functional/NFR-SEC-002.md)
- [NFR-SEC-003: Tokens stay server side](../requirements/non-functional/NFR-SEC-003.md)
- [NFR-SEC-007: sdlc_ui behind Identity-Aware Proxy](../requirements/non-functional/NFR-SEC-007.md)
- [NFR-AUD-001: Audit every decision](../requirements/non-functional/NFR-AUD-001.md)

# Realisation

- Users: Cloud Identity accounts, provisioned from Microsoft Entra ID, with SAML single sign-on to Entra ID.
- Tokens: Google OAuth 2.0 and OpenID Connect. ID tokens are verified against Google's published signing keys;
  access tokens by Google's token introspection, which reports no hosted domain, so the domain is taken from the
  verified email. Verified claims are cached per instance for 300 seconds, or until the token expires.
- The configuration-dependent checks (declared OAuth client and its surface, `openid` and `email` scopes, allowed
  domains, block list, no service accounts) run on every request against the active bundle, so a block or a
  removed client takes effect at the next refresh even for a cached token.
- Allowed domains and the OAuth client IDs of each surface are declared per environment in
  `config/env/<env>/identity.yaml`, which is not committed.
- System identity: a dedicated Google Cloud service account.
- Library `libs/sdlc_identity`, used by user_agent_mcp; Knowledge Search and the sdlc_ui BFF use it when they are
  built.
