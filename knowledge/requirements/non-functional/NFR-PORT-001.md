---
type: Non-Functional Requirement
title: Tenant-agnostic identity
description: The platform can be pointed at another Entra tenant by configuration alone.
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
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

No tenant-specific value shall be fixed in code.

# Acceptance criteria

- Tenant and app IDs come from the environment; group IDs from the git-ignored group map.
- Login and Graph hosts come from `platform.yaml` (or `ENTRA_AUTHORITY_HOST` for the agent web app and oauth2-proxy).
- The code does not assume the `groups` claim is present or complete.
