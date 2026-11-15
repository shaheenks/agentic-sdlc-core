---
type: Functional Requirement
title: Sign-in
description: Every surface requires a valid sign-in, with Microsoft Entra ID on the Entra stack and a Google identity on the GCP stack; each stack refuses the other's tokens.
area: Identity
tags:
- requirement
- functional
- identity
status: draft
priority: must
implementation: live
sources:
- id: arch
  resource: ../../../docs/ARCHITECTURE.md
  title: System architecture
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

The system shall authenticate every user and refuse any request without a valid token for its stack: an Entra token on the Entra stack, a Google ID token on the GCP stack. Each stack refuses the other's tokens.

# Acceptance criteria

- An unauthenticated browser request to the app is sent to sign-in: Entra by oauth2-proxy on the Entra stack; on
  the native GCP stack, IAP (Cloud Identity accounts, signed in through Entra federation), then the UI's own
  server-side Google sign-in for the IAP user.
- On the native stack the UI forwards only a Google ID token that names the IAP user; a session or token of
  another user is refused.
- An MCP request without a valid token is answered 401 and audited as `auth_failure`.
- `whoami` returns the caller's identity (`oid` on the Entra stack, `sub` and email on the GCP stack), teams and roles.
- The GCP stack's verifier refuses an Entra token, and the Entra stack's verifier refuses a Google ID token.

# Notes

Modified by [CH-0021](../../changes/CH-0021.md): per stack (Entra / GCP), design N7 to N10 and N13.

Modified by [CH-0016](../../changes/CH-0016.md): IAP and the UI's server-side sign-in on the native stack.
