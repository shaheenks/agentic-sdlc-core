---
type: Functional Requirement
title: "YAML configuration in config/"
description: "Teams, user groups, grants, workflows, skills, tools, surfaces and sources are declared in schema-validated YAML in the config folder."
tags: [requirement, configuration]
status: draft
x-area: CFG
x-priority: must
x-implementation: planned
---

# Statement

The system shall take its configuration from YAML files in the repository's `config/` folder, each kind
validated against a published schema.

# Acceptance criteria

- Kinds include at least: teams, user groups, roles and grants, workflow catalog entries, skills, tool groups,
  surfaces, knowledge sources, connection providers and trigger subscriptions.
- Each kind has a JSON Schema in `config/`; a file that does not match its schema, or names something that does
  not exist, fails validation.
- Validation runs locally with one command from `config/` and in CI on every change.
