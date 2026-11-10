---
type: Non-Functional Requirement
title: Browser-facing hardening
description: Browser-reachable endpoints are hardened against content sniffing, cross-site requests and developer tooling exposure.
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
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

Endpoints reachable from a browser shall be hardened against content injection and cross-site requests.

# Acceptance criteria

- Artifact downloads are served as attachments with `nosniff` and a CSP sandbox.
- State-changing browser requests (artifact and thread DELETE) require the `X-SDLC-Request: 1` header.
- ADK developer tools are off unless `SDLC_DEV_TOOLS=true`, which is never set outside local development.
