---
type: Component
title: user_agent
description: The interactive ADK root agent that serves people in the chat app, built from skills and MCP tools.
area: Agents
tags:
- component
- agents
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../agents/user_agent
satisfies:
- /requirements/functional/FR-DOC-001
- /requirements/functional/FR-SURF-001
- /requirements/functional/FR-TEAM-002
- /requirements/non-functional/NFR-SEC-001
- /requirements/non-functional/NFR-SEC-006
verified_by:
- tests/e2e/test_stage2_agent.py
sources:
- id: readme
  resource: ../../agents/user_agent/README.md
  title: agents/user_agent/README.md
---

# Purpose

Holds the conversation and reasons with Gemini. Everything it knows or does comes through the MCP server as the signed-in user; it makes no access decisions and never reads `config/`.

Code: `agents/user_agent`

# Responsibilities

- Connects to `core_mcp` with the user's bearer token and the conversation id.
- Loads per-session team instructions through `sdlc_agent.with_team_context`.
- Offers the local tools `goldfish_review` and `set_active_team`.
- Attaches A2UI cards to tool results for A2A clients.

# Depends on

- [sdlc_agent](sdlc_agent.md)
- [sdlc_auth](sdlc_auth.md)
- [core_mcp](core_mcp.md)

# Requirements

- [FR-DOC-001: Reviewed document flow](../requirements/functional/FR-DOC-001.md) - Drives the document flow and calls `goldfish_review`.
- [FR-SURF-001: Chat application](../requirements/functional/FR-SURF-001.md) - Is the agent the chat talks to.
- [FR-TEAM-002: Team resolution and lock](../requirements/functional/FR-TEAM-002.md) - Exposes `set_active_team` to lock the team for a document.
- [NFR-SEC-001: Single enforcement point](../requirements/non-functional/NFR-SEC-001.md) - Makes no authorization decision; holds no config or database access.
- [NFR-SEC-006: Calls are made as the user](../requirements/non-functional/NFR-SEC-006.md) - Sends every MCP call with the user's own token.

# Verification

- `tests/e2e/test_stage2_agent.py`
