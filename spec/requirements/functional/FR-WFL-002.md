---
type: Functional Requirement
title: "Workflow definition"
description: "A workflow is a graph of typed steps: agent, tool, human task and sub-workflow."
tags: [requirement, workflows]
status: draft
x-area: WFL
x-priority: must
x-implementation: planned
---

# Statement

The system shall let a workflow be defined as a graph of agent, tool, human-input, code and sub-workflow nodes with typed inputs and outputs, run in sequence, in parallel or by route conditions.

# Acceptance criteria

- Validation rejects a definition that names an unknown skill, tool, artifact type or step.
- Each agent step declares its skills and the most tools it may use (its ceiling).
- Each step declares its output schema.

# Notes

Realised with ADK 2.0 graph workflows ([DEC-0004](../../decisions/DEC-0004.md)).
