---
type: Component
title: Skill Library
description: Versioned instruction packages that teach an agent step how to do one SDLC task, global or team-specific.
tags: [component, capability, agent]
status: draft
x-layer: capability
x-folder: skills/
x-depends-on: [/components/configuration-registry]
x-satisfies: [/requirements/functional/FR-AUTHZ-002, /requirements/functional/FR-WFL-006, /requirements/functional/FR-AGT-001, /requirements/functional/FR-SKILL-001, /requirements/non-functional/NFR-HOST-001, /requirements/functional/FR-SDLC-004]
---

# Purpose

Skills carry the know-how (how this organisation writes a user story, what a design review checks),
separate from workflow structure and from access rules.

# Responsibilities

- Store skills as content packages (instructions, templates, examples, reference files) with a globally unique name.
- Support global skills and team add-ons that extend or override them for a team.
- Version skills so a run uses exactly the skill versions its workflow version pinned.
- Serve a skill only to a caller whose effective policy includes it.

# Out of scope

- Access rules for skills, declared in configuration and decided by the [Access Policy](access-policy.md).
- Workflow structure: the [Workflow Catalog](workflow-catalog.md).

# Interfaces

- Provides: `get(skill, version)`, `list(identity, team?)`.
- Consumes: skill content published in the [Configuration Registry](configuration-registry.md) bundle.

# Depends on

- [Configuration Registry](configuration-registry.md)

# Owns

- Skill content and version history.

# Requirements

- [FR-AUTHZ-002: Selective disclosure](../requirements/functional/FR-AUTHZ-002.md)
- [FR-WFL-006: Reproducible runs](../requirements/functional/FR-WFL-006.md)
- [FR-AGT-001: Bounded agent steps](../requirements/functional/FR-AGT-001.md)
- [FR-SKILL-001: Skill packages](../requirements/functional/FR-SKILL-001.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [FR-SDLC-004: Fresh-context document review](../requirements/functional/FR-SDLC-004.md)

# Realisation

- Skills are packaged in the latest stable SKILL.md format, in folder `skills/`.
- Built (phase 4a): stage skills `brainstorm`, `features-and-stories` and `design-specification`, and seven
  reviewers (structure, writing style, clarity for a new reader, design decisions, readiness to build, technical
  detail, unnecessary complexity) adapted from the Elephant-Goldfish Model's Goldfish reviewers (Apache-2.0,
  attributed in `skills/NOTICE`). Every reviewer returns findings as JSON with a severity, a location, the problem
  and a suggested change. user_agent's tests load each skill with ADK's skill loader.
