---
type: Functional Requirement
title: "Skill packages"
description: "Agent know-how ships as versioned skill packages, global or team-specific."
tags: [requirement, skills]
status: draft
x-area: SKILL
x-priority: must
x-implementation: planned
---

# Statement

The system shall provide skills as versioned instruction packages, global or team add-ons, served only to callers whose effective policy includes them.

# Acceptance criteria

- Skill names are globally unique.
- A team add-on extends or overrides a global skill for that team's runs only.
- A request for a skill outside the caller's policy is denied.
- Skills use the latest stable SKILL.md package format.
