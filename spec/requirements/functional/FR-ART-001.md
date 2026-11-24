---
type: Functional Requirement
title: "Artifacts with lineage"
description: "Runs store their outputs as artifacts linked to the run and step."
tags: [requirement, artifacts]
status: draft
x-area: ART
x-priority: must
x-implementation: planned
---

# Statement

The system shall store the outputs of a run as artifacts linked to the run and step that produced them.

# Acceptance criteria

- Each artifact records type, owner, run, step, workflow version and classification.
- A run's page lists its artifacts.
