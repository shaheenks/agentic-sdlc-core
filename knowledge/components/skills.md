---
type: Component
title: skills
description: 'SKILL.md instruction packages: global skills and per-team add-ons. Content only.'
area: Content and configuration
tags:
- component
- content-and-configuration
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../skills
satisfies:
- /requirements/functional/FR-DOC-001
- /requirements/functional/FR-SKILL-001
- /requirements/functional/FR-SKILL-002
- /requirements/functional/FR-TEAM-001
verified_by:
- tests/config/test_skills_config.py
- tests/mcp/test_skills.py
- tests/evals/test_team_lens_eval.py
sources:
- id: readme
  resource: ../../skills/README.md
  title: skills/README.md
---

# Purpose

What the assistant knows how to do. Skills carry no access rules; who may load one is declared in `config/`.

Code: `skills`

# Responsibilities

- Global skills in `skills/core/`, including the document flow and review lenses.
- Team add-ons and `AGENT_ADDENDUM.md` in `skills/teams/<team>/`.

# Depends on

- [config](config.md)

# Requirements

- [FR-DOC-001: Reviewed document flow](../requirements/functional/FR-DOC-001.md) - Holds the document-flow, brainstorm and lens skills.
- [FR-SKILL-001: Skills served per user](../requirements/functional/FR-SKILL-001.md) - Is the content served.
- [FR-SKILL-002: Skill naming and layout](../requirements/functional/FR-SKILL-002.md) - Follows the naming and layout rules.
- [FR-TEAM-001: Team customization of behaviour](../requirements/functional/FR-TEAM-001.md) - Holds team add-on skills and instructions.

# Verification

- `tests/config/test_skills_config.py`
- `tests/mcp/test_skills.py`
- `tests/evals/test_team_lens_eval.py`
