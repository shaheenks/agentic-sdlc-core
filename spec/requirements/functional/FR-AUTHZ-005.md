---
type: Functional Requirement
title: "Rate limits and quotas"
description: "Runs started and tool calls are limited per user and per team."
tags: [requirement, authorization]
status: draft
x-area: AUTHZ
x-priority: should
x-implementation: planned
---

# Statement

The system shall apply the rate limits and quotas declared in configuration per user and per team.

# Acceptance criteria

- Limits on runs started and tool calls per period are declared per role or team.
- A request over a limit is refused with a reason the surface can show, and the refusal is audited.

# Notes

Counted per service instance until an operations database exists, so limits are approximate ([DEC-0003](../../decisions/DEC-0003.md)).
