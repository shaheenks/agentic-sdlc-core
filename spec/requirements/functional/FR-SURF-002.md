---
type: Functional Requirement
title: "A2A router"
description: "Gemini Enterprise, and later third-party A2A surfaces, reach user_agent through one A2A router, as the calling user."
tags: [requirement, surfaces]
status: draft
x-area: SURF
x-priority: must
x-implementation: planned
---

# Statement

The system shall provide one Agent2Agent (A2A) router in front of user_agent, through which Gemini Enterprise and, once enabled, third-party A2A surfaces run workflows and ad-hoc chat, acting as the calling user.

# Acceptance criteria

- The endpoint publishes an agent card whose skills are workflows; an authenticated caller is offered only the workflows they may start.
- A request without a valid Google-issued token for a user of the organisation's Cloud Identity account is refused with 401, and no workflow is listed or started.
- A run started over A2A is reported as an A2A task that the client can poll or subscribe to until it completes.
- A run started over A2A appears in the caller's run history in sdlc_ui.
- The endpoint implements the latest stable A2A protocol version (1.0 when this was written), declares it in the
  agent card, and honours the `A2A-Version` header; older versions are added only for a declared client that needs one.
- The agent card declares an OAuth 2.0 security scheme with Google's authorization and token endpoints, so any A2A client can run the sign-in flow without platform-specific code.

# Notes

Gemini Enterprise uses the router now ([FR-SURF-003](FR-SURF-003.md)); Microsoft Copilot and other third-party surfaces use the same router once enabled ([FR-SURF-005](FR-SURF-005.md), parked).

Whether the public agent card lists any workflow, or only the authenticated extended card does, is open. Third-party AI surfaces use this endpoint: [FR-SURF-005](FR-SURF-005.md).

# Citations

[1] [Announcing A2A 1.0](https://raw.githubusercontent.com/a2aproject/A2A/main/docs/announcing-1.0.md)
[2] [What's new in A2A v1](https://raw.githubusercontent.com/a2aproject/A2A/main/docs/whats-new-v1.md)
