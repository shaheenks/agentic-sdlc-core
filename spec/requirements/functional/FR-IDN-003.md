---
type: Functional Requirement
title: "Block list"
description: "A blocked user is refused on every surface."
tags: [requirement, identity]
status: draft
x-area: IDN
x-priority: should
x-implementation: planned
---

# Statement

The system shall refuse every request from a user on the block list declared in configuration.

# Acceptance criteria

- A blocked user's requests get 401 on every surface once the configuration that blocks them is active.
- A running run that acts for a blocked user is paused before its next step.
