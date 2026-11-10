---
type: Non-Functional Requirement
title: Production identity hardening
description: Production uses federated credentials and Terraform-managed Entra apps, with no development shortcuts.
area: Portability
tags:
- requirement
- non-functional
- portability
status: stable
priority: should
implementation: parked
verified:
- by: human:shaheenks
  at: '2026-11-10T21:45:18+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
- id: v03
  resource: ../../../docs/plans/version-03.md
  title: Implementation plan version-03
---

# Statement

Production shall use Terraform-managed Entra applications and certificates or federated credentials, with no development-only shortcuts.

# Acceptance criteria

- No client secrets, Azure CLI pre-authorization or script-based provisioning in production.

# Notes

Parked 2026-11-07 (version-03 P2, E4 to E6).
