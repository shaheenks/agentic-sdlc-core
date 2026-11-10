---
type: Non-Functional Requirement
title: Strict token validation
description: Only Entra v2 user tokens for this tenant and API are accepted.
area: Security
tags:
- requirement
- non-functional
- security
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:30:44+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
---

# Statement

The system shall accept only tokens issued by the configured Entra tenant for this API, and validate them fully on every request.

# Acceptance criteria

- Checked on every request: v2 issuer, audience, `tid`, signature against JWKS, and expiry.
- User tokens must carry the `access_as_user` scope.
- The agent web app re-validates the token it receives from oauth2-proxy and binds the user to its `oid`.
