---
type: Functional Requirement
title: Skill naming and layout
description: Skill names are stable, globally unique identifiers validated at load.
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
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

The system shall validate skill names and layout when configuration loads.

# Acceptance criteria

- Names are lowercase kebab-case and unique across the global catalog and every team's add-ons.
- Folder name, `SKILL.md` frontmatter `name` and config key are the same.
- A duplicate name fails validation.
