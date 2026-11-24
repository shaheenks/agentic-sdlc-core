---
type: Non-Functional Requirement
title: "Reproducible images"
description: "Each deployable image is identified by its build inputs and promoted unchanged."
tags: [requirement, operability]
status: draft
x-area: OPS
x-priority: should
x-implementation: planned
---

# Statement

The system shall tag each deployable image by its build inputs and promote the same image between environments.

# Acceptance criteria

- Rebuilding from unchanged inputs yields the same tag.
- Production runs only images that ran in an earlier environment.
