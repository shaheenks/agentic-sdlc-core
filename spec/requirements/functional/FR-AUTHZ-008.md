---
type: Functional Requirement
title: "Per-user isolation of sessions, artifacts and secrets"
description: "A user's sessions, artifacts and connection secrets belong to that user alone and are not visible to anyone else."
tags: [requirement, authz, security, privacy]
status: draft
x-area: AUTHZ
x-priority: must
x-implementation: planned
---

# Statement

The system shall keep each user's sessions, artifacts and connection secrets visible and usable only by that user, and by no other user, team member or administrator through any surface.

# Acceptance criteria

- The owner of a session, artifact or connection is the user ID (the Google account's stable `sub`) in the verified token of the request that created it; it is never taken from a tool argument.
- Listing sessions, run history, artifacts or connections returns only the caller's own.
- A request for another user's session, artifact or connection is answered as not found and audited.
- Storage paths are built by the server from the verified user ID; a tool argument names an artifact or provider, never a path, and a name that would leave the user's prefix is refused.
- Runs are still labelled with their team for policy and reporting, but a team label grants no access to them.
- Scheduled and event-triggered runs, which act as the system identity, are not visible through any user's surface.

# Notes

Team visibility of runs and artifacts ([FR-TEAM-003](FR-TEAM-003.md), parked) and artifact sharing ([FR-ART-002](FR-ART-002.md)) are out of scope for now. Human tasks assigned to someone other than the run's user ([FR-HUM-002](FR-HUM-002.md), [FR-HUM-004](FR-HUM-004.md)) need a rule of their own; see the open question in [Human Tasks](../../components/human-tasks.md).
