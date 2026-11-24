---
type: Functional Requirement
title: "Task signals inside the platform"
description: "Open human tasks are signalled to their user inside the platform only; there are no reminders, expiry or outside notifications."
tags: [requirement, human-tasks]
status: draft
x-area: HUM
x-priority: should
x-implementation: planned
---

# Statement

The system shall signal a user's open human tasks to that user inside the platform.

# Acceptance criteria

- sdlc_ui shows a count of open tasks on the inbox.
- When the user opens the chat in sdlc_ui or starts a new Gemini Enterprise conversation, user_agent lists
  the tasks waiting for them.
- No message about a task is sent outside the platform; findings reach people as Jira tasks instead
  ([FR-SDLC-012](FR-SDLC-012.md)).
- A task waits until it is answered or the run is cancelled; it has no due time, reminder or expiry.

# Notes

Reminders, escalation and expiry are not needed for now; add them as a new requirement if they are needed later.
