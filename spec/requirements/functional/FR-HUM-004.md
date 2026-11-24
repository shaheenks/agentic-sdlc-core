---
type: Functional Requirement
title: "Separation of duties"
description: "Where a step requires it, the run's starter cannot approve their own run."
tags: [requirement, human-tasks]
status: draft
x-area: HUM
x-priority: should
x-implementation: parked
---

# Statement

The system shall refuse an approval from the run's starter on a step that declares separation of duties.

# Acceptance criteria

- On such a step the starter is excluded from the assignees, even when they are in the assigned team.

# Notes

Parked: tasks are answered only by the run's own user ([FR-HUM-002](FR-HUM-002.md)), so nobody else can approve. Returns with team assignment.
