---
type: Functional Requirement
title: "Authorize every call"
description: "Every workflow start, tool call and resource access is authorized, with its arguments, when it is made."
tags: [requirement, authorization]
status: draft
x-area: AUTHZ
x-priority: must
x-implementation: planned
---

# Statement

The system shall authorize every workflow start, tool call and resource access, including its arguments, at the time it is made.

# Acceptance criteria

- A call to a tool that was not listed to the caller is denied, even if the model names it.
- Argument constraints, such as the repositories a tool may touch, are checked on each call and a violation is denied.
- Each decision names the rule that matched.
