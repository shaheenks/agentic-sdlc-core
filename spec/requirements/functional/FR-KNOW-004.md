---
type: Functional Requirement
title: "Knowledge scope: broad in chat, team in workflows"
description: "Ad-hoc knowledge search and brainstorming use everything the user may read; a predefined workflow sets the team scope when it starts, and changing it needs the user's explicit confirmation in chat."
tags: [requirement, know, knowledge, authz]
status: draft
x-area: KNOW
x-priority: must
x-implementation: planned
---

# Statement

The system shall search all knowledge the user may read in ad-hoc chat, limit a predefined workflow run to the sources of the team the run is for, and change a run's team scope only after the user confirms it in chat.

# Acceptance criteria

- In ad-hoc knowledge search and brainstorming ([FR-AGT-005](../functional/FR-AGT-005.md)), the scope is every source the user may read through any of their teams, never more ([FR-AUTHZ-004](../functional/FR-AUTHZ-004.md)).
- When a predefined workflow starts, its team scope is set to the team the run is for (chosen or confirmed by the user) and kept for the whole run, including after resuming.
- A change of team scope during a run, asked for by the user or proposed by the agent, takes effect only after the user explicitly confirms it in chat; the new team must be one of the user's teams.
- Every scope change is recorded on the run and audited with the old and new team.
- user_agent_mcp builds the filter attribute from the scope held for the session; a tool argument cannot widen it.
