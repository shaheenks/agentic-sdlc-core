---
type: Component
title: copilotkit
description: 'The CopilotKit (Next.js) chat app at /chat/: conversation, history, artifacts panel and viewer, Connections page.'
area: User interface
tags:
- component
- user-interface
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../ui/copilotkit
satisfies:
- /requirements/functional/FR-ART-003
- /requirements/functional/FR-CONN-001
- /requirements/functional/FR-CONV-001
- /requirements/functional/FR-DOC-001
- /requirements/functional/FR-KNOW-002
- /requirements/functional/FR-SURF-001
- /requirements/non-functional/NFR-SEC-006
verified_by:
- ui/copilotkit/tests
sources:
- id: readme
  resource: ../../ui/copilotkit/README.md
  title: ui/copilotkit/README.md
---

# Purpose

The main surface. It talks AG-UI to the agent, forwards only the user's access token, and keeps no conversations of its own.

Code: `ui/copilotkit`

# Responsibilities

- Chat with purpose-built renderers for tool results.
- History sidebar: list, open with replay, delete.
- Artifacts panel and viewer with numbered lines, line comments and versions.
- Connections page and navbar status.

# Depends on

- [sdlc_web](sdlc_web.md)
- [core_mcp](core_mcp.md)

# Requirements

- [FR-ART-003: Download and review artifacts in the chat](../requirements/functional/FR-ART-003.md) - Artifacts panel and viewer.
- [FR-CONN-001: Users connect their own accounts](../requirements/functional/FR-CONN-001.md) - Connections page.
- [FR-CONV-001: Conversation history](../requirements/functional/FR-CONV-001.md) - History sidebar.
- [FR-DOC-001: Reviewed document flow](../requirements/functional/FR-DOC-001.md) - Shows the review card and the team-lock line.
- [FR-KNOW-002: Knowledge search with citations](../requirements/functional/FR-KNOW-002.md) - Shows citations as chips.
- [FR-SURF-001: Chat application](../requirements/functional/FR-SURF-001.md) - Is the chat application.
- [NFR-SEC-006: Calls are made as the user](../requirements/non-functional/NFR-SEC-006.md) - Forwards only `X-Forwarded-Access-Token` to the agent.

# Verification

- `ui/copilotkit/tests`
