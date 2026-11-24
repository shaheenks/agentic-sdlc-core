---
type: Functional Requirement
title: "Selective disclosure"
description: "Users and their agents are shown only what the user may use."
tags: [requirement, authorization]
status: draft
x-area: AUTHZ
x-priority: must
x-implementation: planned
---

# Statement

The system shall list to a user, and to agents acting for them, only the workflows, tools, skills and knowledge sources that user's effective policy allows.

# Acceptance criteria

- The tool list an agent step receives holds only tools that are both in the step's ceiling and allowed for the user.
- Workflow lists on every surface are filtered by the user's effective policy.
