---
type: Functional Requirement
title: "Ad-hoc knowledge search and brainstorm chat"
description: "Users chat with user_agent outside any workflow, to search knowledge and brainstorm, acting as themselves."
tags: [requirement, agt, chat, knowledge]
status: draft
x-area: AGT
x-priority: must
x-implementation: planned
---

# Statement

The system shall let a user chat with user_agent outside any workflow, to search the knowledge they may read and to brainstorm, acting with the user's own identity.

# Acceptance criteria

- The chat is available in sdlc_ui and in Gemini Enterprise (through the [A2A router](FR-SURF-002.md)).
- Knowledge answers come from knowledge search within the user's data scope ([FR-AUTHZ-004](FR-AUTHZ-004.md)) and cite the source of each result ([FR-KNOW-002](FR-KNOW-002.md)).
- In ad-hoc chat the knowledge scope is broad: every source the user may read ([FR-KNOW-004](FR-KNOW-004.md)).
- The chat uses only the tools of the tool groups declared for chat in configuration, through user_agent_mcp ([FR-AUTHZ-006](FR-AUTHZ-006.md)).
- The chat can suggest a workflow and start it when the user asks; the run then follows the workflow's own rules and team scope.
- A chat session belongs to its user, is visible to no one else ([FR-AUTHZ-008](FR-AUTHZ-008.md)), and can be resumed after signing in again ([FR-WFL-009](FR-WFL-009.md)).
