---
type: Functional Requirement
title: Role hierarchy with classification ceilings
description: Roles inherit from one another and each caps the data classification its holder can read.
area: Authorization
tags:
- requirement
- functional
- authorization
status: draft
priority: must
implementation: live
sources:
- id: design
  resource: ../../../docs/designs/workflow-platform.md
  title: Workflow platform target design
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

The system shall provide inheriting platform roles and team roles, each with a maximum data classification, and give every signed-in user a minimal role.

# Acceptance criteria

- Platform roles, bound globally: `viewer` (internal: the common knowledge sources, skills and tools) and `admin` (restricted, unconstrained: every platform capability).
- Team roles, bound per team: `member` (every team member: the team's skills, tools and knowledge sources) and the optional `approver` (inherits `member`: the team's approval and elevated-access skills and tools, and its confidential sources).
- Workflow roles (FR-IDN-005) are declared like any other role and bound to Entra app roles.
- A signed-in user with no other grant can use only `ping` and `whoami`.

# Notes

Modified by CH-0008 (design D4). The config ids are `developer` and `lead` today; [CH-0009](../../changes/CH-0009.md) renames them. Team scoping is [FR-AUTHZ-006](FR-AUTHZ-006.md).
