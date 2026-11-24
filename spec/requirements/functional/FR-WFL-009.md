---
type: Functional Requirement
title: "Resume after signing in again"
description: "A user who signs out, or whose sign-in expires, signs in again and continues their own sessions and waiting runs."
tags: [requirement, wfl]
status: draft
x-area: WFL
x-priority: must
x-implementation: planned
---

# Statement

The system shall let a user who signs in again, on the same or another surface session, list and continue their own sessions and runs, including runs waiting on their input.

# Acceptance criteria

- Sessions are keyed by the user ID, not by a token or a browser session; a new token for the same user finds the same sessions.
- A run waiting on a human-input node continues when the user answers after signing in again, with the token of the new sign-in; no earlier token is stored or reused.
- Expiry of a token never fails or cancels a run that is waiting; it fails only a request made with it.
- In sdlc_ui, an expired sign-in is refreshed silently where possible; otherwise the user signs in again and returns to the page they were on.
- In the Gemini Enterprise app, reopening a past conversation continues its session.
- Agent steps are expected to finish within the user's session. A step that stops because the user's token expired is resumed from the session history after the user signs in again, without repeating finished steps.

# Notes

Run state lives in the run's Agent Runtime session ([DEC-0003](../../decisions/DEC-0003.md), [DEC-0004](../../decisions/DEC-0004.md)), so nothing is lost when a token expires. To verify: that the Gemini Enterprise app resumes a past conversation with the same Agent Runtime session ID and passes a fresh token on each turn.
