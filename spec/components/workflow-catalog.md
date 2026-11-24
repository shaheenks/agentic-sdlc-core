---
type: Component
title: Workflow Catalog
description: The library of pre-defined, versioned SDLC workflow definitions - their steps, inputs, outputs, gates and who may run them.
tags: [component, control, workflow]
status: draft
x-layer: control
x-depends-on: [/components/configuration-registry, /components/skill-library]
x-satisfies: [/requirements/functional/FR-SURF-001, /requirements/functional/FR-SURF-002, /requirements/functional/FR-AUTHZ-002, /requirements/functional/FR-WFL-001, /requirements/functional/FR-WFL-002, /requirements/functional/FR-WFL-005, /requirements/functional/FR-WFL-006, /requirements/functional/FR-WFL-007, /requirements/functional/FR-MDL-001, /requirements/non-functional/NFR-HOST-001, /requirements/non-functional/NFR-ARCH-005, /requirements/non-functional/NFR-PERF-001]
---

# Purpose

Users do not compose agents; they run workflows someone has designed, reviewed and published. The
catalog is that published set, for example "user story from a Jira epic", "design review", "test
plan from a PR", "release notes".

# Responsibilities

- Define each workflow as a versioned definition: inputs and their schema, ordered or branching steps, step kinds (agent step, tool step, human task, sub-workflow), outputs and artifact types.
- Bind each agent step to the skills it uses and the tools it may call: a ceiling the [Access Policy](access-policy.md) narrows further per user.
- Declare scope (global or team-specific variants), the triggers it accepts and the run limits (time, cost, steps).
- Validate definitions: every referenced skill, tool and artifact type exists; no step can exceed its declared tools.
- Keep old versions so running and past runs stay reproducible.

# Out of scope

- Running workflows: the [Workflow Engine](workflow-engine.md).
- Instruction content for the model: the [Skill Library](skill-library.md).

# Interfaces

- Provides: `list(identity, team?)` (filtered by policy), `get(workflow_id, version)`.
- Consumes: definitions published in the [Configuration Registry](configuration-registry.md) bundle.

# Depends on

- [Configuration Registry](configuration-registry.md)
- [Skill Library](skill-library.md)

# Owns

- Workflow definitions and their version history.

# Requirements

- [FR-SURF-001: Custom UI](../requirements/functional/FR-SURF-001.md)
- [FR-SURF-002: A2A router](../requirements/functional/FR-SURF-002.md)
- [FR-AUTHZ-002: Selective disclosure](../requirements/functional/FR-AUTHZ-002.md)
- [FR-WFL-001: Workflow catalog](../requirements/functional/FR-WFL-001.md)
- [FR-WFL-002: Workflow definition](../requirements/functional/FR-WFL-002.md)
- [FR-WFL-005: Run limits](../requirements/functional/FR-WFL-005.md)
- [FR-WFL-006: Reproducible runs](../requirements/functional/FR-WFL-006.md)
- [FR-WFL-007: Team parameter overrides](../requirements/functional/FR-WFL-007.md)
- [FR-MDL-001: Model classes](../requirements/functional/FR-MDL-001.md)
- [NFR-HOST-001: Hosted on Google Cloud](../requirements/non-functional/NFR-HOST-001.md)
- [NFR-ARCH-005: Google ADK agents and graph workflows](../requirements/non-functional/NFR-ARCH-005.md)
- [NFR-PERF-001: Application response under 5 seconds on average](../requirements/non-functional/NFR-PERF-001.md)

# Realisation

- Teams cannot fork a global workflow; a team overrides only the parameters the workflow declares as overridable.
- Catalog entries are YAML in `config/`; workflow graphs are ADK code in `interactive_agents/user_agent/` ([DEC-0004](../decisions/DEC-0004.md)).
