---
type: Functional Requirement
title: "Reconnect instead of fail"
description: "A run that needs a missing or expired connection asks the user to connect."
tags: [requirement, connections]
status: draft
x-area: CONN
x-priority: should
x-implementation: planned
---

# Statement

The system shall pause a run whose step needs a connection the user lacks, or whose connection has expired, and ask the user to connect.

# Acceptance criteria

- The run waits on a task that links to the connection page.
- Once the user connects, the step retries.
