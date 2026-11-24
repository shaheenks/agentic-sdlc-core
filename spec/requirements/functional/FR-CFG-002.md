---
type: Functional Requirement
title: "Permission diff"
description: "Reviewers see who gains or loses what between two configuration versions."
tags: [requirement, configuration]
status: draft
x-area: CFG
x-priority: should
x-implementation: planned
---

# Statement

The system shall show, for two configuration versions, which users and teams gain or lose which workflows, tools, skills and data.

# Acceptance criteria

- The diff runs in CI on every configuration change and is shown to the reviewer.
- The diff can be produced locally for any two versions.
