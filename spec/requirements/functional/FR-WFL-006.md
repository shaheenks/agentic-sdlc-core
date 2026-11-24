---
type: Functional Requirement
title: "Reproducible runs"
description: "A run uses exactly the workflow and skill versions pinned when it started."
tags: [requirement, workflows]
status: draft
x-area: WFL
x-priority: must
x-implementation: planned
---

# Statement

The system shall run each run with the workflow, skill and configuration versions pinned when it started.

# Acceptance criteria

- Publishing a new workflow version does not change runs already started.
- A run's record shows the exact versions it used.
