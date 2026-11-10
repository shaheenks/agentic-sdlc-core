---
type: Functional Requirement
title: Access declared in configuration
description: Roles, teams, tools, skills, sources and limits are declared in versioned YAML, never in code.
area: Configuration
tags:
- requirement
- functional
- configuration
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:10:40+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
---

# Statement

The system shall take all access rules from declarative configuration files and reject configuration it does not fully understand.

# Acceptance criteria

- Every config file has `apiVersion: sdlc/v1` and a `kind`; unknown keys or references fail validation.
- No role, group, tool list or data scope is hard-coded in code.
- `sdlc-config validate --env <env>` passes before a change is merged.
