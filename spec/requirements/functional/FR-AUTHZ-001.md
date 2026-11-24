---
type: Functional Requirement
title: "Access declared in configuration"
description: "All access rules come from declarative configuration, never from code or prompts."
tags: [requirement, authorization]
status: draft
x-area: AUTHZ
x-priority: must
x-implementation: built
---

# Statement

The system shall take every access rule (roles, grants, team bindings, tool lists, data scopes) from declarative configuration.

# Acceptance criteria

- Changing a grant needs only a configuration change and its activation; no code changes or redeploys.
- No component's code names a role, group, team or tool list.
- Agent and skill instructions carry no access rules.
