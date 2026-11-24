---
type: Functional Requirement
title: "Task routing"
description: "Every human task is assigned to the user whose run raised it; routing to other users, teams or team roles is not needed for now."
tags: [requirement, human-tasks]
status: draft
x-area: HUM
x-priority: must
x-implementation: planned
---

# Statement

The system shall assign each human task to the user whose run raised it, and accept an answer only from that user.

# Acceptance criteria

- An answer from anyone else is refused, answered as not found, and audited
  ([FR-AUTHZ-008](FR-AUTHZ-008.md)).
- The task records when it was answered and with what comment.
- A workflow that declares a task for another user, a team or a team role fails validation when it is published.
- A task is answered in sdlc_ui, in the Gemini Enterprise conversation for runs started there ([FR-SURF-003](FR-SURF-003.md)), or by an approval in Jira, Confluence or Git where the step declares one; there is no other channel.

# Notes

Tasks are answered only by the run's own user for now. Assignment to teams and
team roles can return as a new requirement.
