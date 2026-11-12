---
type: Non-Functional Requirement
title: Tenant-agnostic identity
description: The platform can be pointed at another Entra tenant by configuration alone.
area: Portability
tags:
- requirement
- non-functional
- portability
status: draft
priority: must
implementation: live
sources:
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

No tenant-specific value shall be fixed in code.

# Acceptance criteria

- Tenant and app IDs come from the environment. App-role values are configuration, not tenant data.
- The login host comes from `platform.yaml` (or `ENTRA_AUTHORITY_HOST` for the agent web app and oauth2-proxy).

# Notes

Edited by CH-0011: the group map, the Graph host (carried over from CH-0005) and the `groups` claim criterion are removed.
