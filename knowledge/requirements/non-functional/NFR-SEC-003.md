---
type: Non-Functional Requirement
title: Strict token validation
description: Only Entra v2 user tokens for this tenant and API (Entra stack), or Google ID tokens for our OAuth client and domain (GCP stack), are accepted.
area: Security
tags:
- requirement
- non-functional
- security
status: draft
priority: must
implementation: live
sources:
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

The system shall accept only tokens from the stack's configured issuer for this API, and validate them fully on every request.

# Acceptance criteria

- Entra stack, checked on every request: v2 issuer, audience, `tid`, signature against JWKS, and expiry.
- Entra user tokens must carry the `access_as_user` scope.
- The agent web app re-validates the token it receives from oauth2-proxy and binds the user to its `oid`.
- GCP stack: a Google ID token is accepted only with issuer `https://accounts.google.com`, an allowed audience (our OAuth client IDs), `email_verified` true and an allowed `hd`, with signature against Google's JWKS and expiry; the user is `sub`.

# Notes

Modified by [CH-0021](../../changes/CH-0021.md): per stack (Entra / GCP), design N7 to N10 and N13.
