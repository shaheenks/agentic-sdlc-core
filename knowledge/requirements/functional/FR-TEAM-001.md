---
type: Functional Requirement
title: Team customization of behaviour
description: Teams add instructions, skills and document-flow defaults that change behaviour but never permissions.
area: Teams
tags:
- requirement
- functional
- teams
status: stable
priority: should
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:13:57+05:30'
sources:
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
---

# Statement

The system shall let a team customize the assistant's behaviour without changing anyone's permissions.

# Acceptance criteria

- A team add-on consists of instructions, add-on skills, tags and document-flow defaults.
- Add-on tags come only from the platform's `skills.team_tags` list and grant nothing.
- Team document-flow caps may only lower the platform's.
