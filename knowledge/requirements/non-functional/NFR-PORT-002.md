---
type: Non-Functional Requirement
title: Configurable endpoints
description: Hostnames and public URLs are configuration; development works on localhost and through the tunnel.
area: Portability
tags:
- requirement
- non-functional
- portability
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:45:18+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
---

# Statement

Hostnames and public URLs shall be configuration, and development shall work both on localhost and through the public tunnel.

# Acceptance criteria

- Hosts come from `SDLC_APP_HOST`, `SDLC_MCP_HOST` and `MCP_PUBLIC_URL`; code never assumes `localhost` or a tunnel.
- Changes to sign-in, cookies or URLs are tested on both the localhost and the tunnel path.
