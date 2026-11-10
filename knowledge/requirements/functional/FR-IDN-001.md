---
type: Functional Requirement
title: Sign-in with Entra ID
description: Every surface requires a valid Microsoft Entra ID sign-in; there is no other identity provider.
area: Identity
tags:
- requirement
- functional
- identity
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:10:40+05:30'
sources:
- id: arch
  resource: ../../../docs/ARCHITECTURE.md
  title: System architecture
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

The system shall authenticate every user through Microsoft Entra ID and refuse any request that does not carry a valid Entra token.

# Acceptance criteria

- An unauthenticated browser request to the app is sent to Entra sign-in by oauth2-proxy.
- An MCP request without a valid token is answered 401 and audited as `auth_failure`.
- `whoami` returns the caller's identity (`oid`), teams and roles.
