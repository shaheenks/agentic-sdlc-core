---
type: Non-Functional Requirement
title: Controlled egress
description: Outbound HTTP goes only to allowlisted hosts.
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
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
---

# Statement

Outbound HTTP to external systems shall go only to hosts on the platform allowlist.

# Acceptance criteria

- Remote HTTP goes through `sdlc_connectors.http.HttpClient`, which checks the allowlist on every request and every redirect.
- A new remote host must be added to `platform.yaml` `knowledge.allowed_hosts`.
