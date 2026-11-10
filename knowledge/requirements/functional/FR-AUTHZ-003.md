---
type: Functional Requirement
title: Role hierarchy with classification ceilings
description: Roles inherit from one another and each caps the data classification its holder can read.
area: Authorization
tags:
- requirement
- functional
- authorization
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:10:40+05:30'
sources:
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
---

# Statement

The system shall provide inheriting roles, each with a maximum data classification, and give every signed-in user a minimal role.

# Acceptance criteria

- Roles are `signed-in`, `viewer` (internal), `developer`, `lead` (confidential) and `admin` (restricted, unconstrained).
- A signed-in user with no other grant can use only `ping` and `whoami`.
