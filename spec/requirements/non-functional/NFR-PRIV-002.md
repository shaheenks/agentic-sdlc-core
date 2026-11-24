---
type: Non-Functional Requirement
title: "Run transcripts under run access"
description: "Agent transcripts are kept only as part of the run, under the run's access rules and retention."
tags: [requirement, privacy]
status: draft
x-area: PRIV
x-priority: should
x-implementation: planned
---

# Statement

The system shall store agent transcripts only as part of their run, readable under the run's access rules and deleted with the run's retention.

# Acceptance criteria

- A user who cannot read a run cannot read its transcripts.
