---
type: Functional Requirement
title: "Bounded agent steps"
description: "An agent step uses only its bound skills and permitted tools, and returns output in its declared schema."
tags: [requirement, agent-steps]
status: draft
x-area: AGT
x-priority: must
x-implementation: planned
---

# Statement

The system shall run each agent step with only the skills bound to it and the tools both in its ceiling and allowed for the user, and return output that matches the step's schema.

# Acceptance criteria

- The model is offered no tool outside the step's ceiling and the user's policy.
- Output that does not match the schema fails the step, after any retries the step declares.
