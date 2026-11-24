---
type: Functional Requirement
title: "Workflow catalog"
description: "Users run pre-defined workflows that authors define, review and publish."
tags: [requirement, workflows]
status: draft
x-area: WFL
x-priority: must
x-implementation: planned
---

# Statement

The system shall offer a catalog of pre-defined workflows that authors define, review and publish, and that users run without changing their structure.

# Acceptance criteria

- A workflow's steps are an ADK graph workflow in `interactive_agents/user_agent/`; its catalog entry (name, inputs, outputs, owner, availability) is YAML in `config/`, published in the configuration bundle.
- Each workflow has a name, description, owner, inputs, outputs and scope (global or team).
- A user supplies only the inputs the workflow declares.
