---
type: Functional Requirement
title: "Run events and history"
description: "Surfaces follow a run live and list past runs."
tags: [requirement, workflows]
status: draft
x-area: WFL
x-priority: must
x-implementation: planned
---

# Statement

The system shall emit an ordered event stream for each run and keep a history of runs that users can list and filter.

# Acceptance criteria

- Each step start, finish, failure and human-task wait emits an event, in order.
- Events are node-level (step by step): agent output appears when a node finishes, not token by token.
- Run history lists the caller's own runs with status, filterable by workflow, team, status and time.

# Notes

Without an operations database, history is listed from Agent Runtime Sessions by user ID only ([DEC-0003](../../decisions/DEC-0003.md), [FR-AUTHZ-008](FR-AUTHZ-008.md)). Step-by-step output was accepted by the user on 2026-11-22; ADK graph workflows do not stream agent output live ([DEC-0004](../../decisions/DEC-0004.md)).
