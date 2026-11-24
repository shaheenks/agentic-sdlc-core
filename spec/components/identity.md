---
type: Component
title: Identity
description: Establishes who the user of each request is, under the environment's identity mode, and refuses anyone it cannot verify.
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

- For now ([DEC-0010](../decisions/DEC-0010.md)): accept a user forwarded by a declared caller (sdlc_ui, the agent runtime) in `X-SDLC-User-Id` and `X-SDLC-User-Email`, the caller proven by its service account's Google ID token for the receiving service; each caller names its surface. Without caller proof only in the local environment.
- When `identity.mode` is `oauth` ([DEC-0001](../decisions/DEC-0001.md), [DEC-0009](../decisions/DEC-0009.md), suspended): verify the user's own Google-issued token, issued to one of the platform's OAuth clients, which names the surface.
- Verify Google-issued tokens, ID tokens locally against Google's keys and access tokens by introspection, caching each verified token per instance for 300 seconds or until it expires if sooner.
- Give every request the stable Google account ID and the account's email, in an allowed domain; group membership comes from the [Directory](directory.md).
- Represent the system identity of unattended runs, a dedicated service account, as a distinct non-human identity.
- Apply the block list; a blocked or unverifiable caller is refused (fail closed).
- Obtain delegated tokens so downstream calls are made as the user where the provider supports it.
- Record each authentication failure and its reason in the [Audit Log](audit-log.md), never the token.

# Out of scope

- What the user may do: the [Access Policy](access-policy.md).
- Team membership: the [Directory](directory.md).
- User accounts and sign-in: Cloud Identity, federated to Microsoft Entra ID.

# Interfaces

- Provides: `identify(headers) -> Identity` (account ID, email, surface, caller); OAuth protected-resource metadata for clients.
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
- Library `libs/sdlc_identity`, used by user_agent_mcp. `identity.mode` in `config/env/<env>/identity.yaml`
  chooses how the user is established ([DEC-0010](../decisions/DEC-0010.md)):
  - `caller_token`: the caller's `Authorization: Bearer` must be a Google ID token whose audience is the
    service's `PUBLIC_URL` (or that URL with `/mcp`) and whose account is listed under `identity.callers` for a
    surface. The user is taken from `X-SDLC-User-Id` (IAP's `accounts.google.com:` prefix accepted) and
    `X-SDLC-User-Email`.
  - `trusted_header`: the same user headers with `X-SDLC-Surface` naming a declared caller's surface and no
    proof; refused by the configuration compiler and by the service in any environment but `local`.
  - `oauth`: the user's own Google token, issued to an OAuth client listed under `identity.clients` for a
    surface, with the `openid` and `email` scopes. ID tokens are verified against Google's published signing
    keys; access tokens by Google's token introspection.
- In every mode the account ID must be a plain identifier and the email well-formed, in an allowed domain, not
  a service account and not on the block list. These checks run on every request against the active bundle,
  so a block takes effect at the next refresh. Verified tokens are cached per instance for 300 seconds, or
  until they expire.
- System identity: a dedicated Google Cloud service account.
