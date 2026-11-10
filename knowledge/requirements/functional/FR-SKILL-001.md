---
type: Functional Requirement
title: Skills served per user
description: Users see and load only the skills their policy allows.
area: Skills
tags:
- requirement
- functional
- skills
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:13:57+05:30'
sources:
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

The system shall list and serve to each user only the skills their policy allows.

# Acceptance criteria

- `list_skills` returns the visible skills with their tags and team.
- `load_skill` on a hidden skill answers 'unknown skill'; the real reason is recorded only in the audit.
- Skill files hold content only; access is declared in configuration.
