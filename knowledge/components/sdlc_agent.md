---
type: Component
title: sdlc_agent
description: 'Agent helpers: per-session team context, the team lock, Goldfish reviewers and A2UI cards.'
area: Libraries
tags:
- component
- libraries
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../libs/sdlc_agent
satisfies:
- /requirements/functional/FR-DOC-001
- /requirements/functional/FR-SURF-002
- /requirements/functional/FR-TEAM-001
- /requirements/functional/FR-TEAM-002
- /requirements/non-functional/NFR-SEC-009
verified_by:
- tests/agent
sources:
- id: readme
  resource: ../../libs/sdlc_agent/README.md
  title: libs/sdlc_agent/README.md
---

# Purpose

Shared building blocks for ADK agents. Everything that needs the user's permissions is asked of the MCP server as the user.

Code: `libs/sdlc_agent`

# Responsibilities

- `with_team_context`: per-session instructions from `get_agent_context`.
- `set_active_team`: locks a team in server-side session state after checking membership.
- `goldfish_review`: parallel isolated reviewers and a synthesizer.
- A2UI card builder with strict validation.

# Depends on

- [sdlc_auth](sdlc_auth.md)
- [core_mcp](core_mcp.md)

# Requirements

- [FR-DOC-001: Reviewed document flow](../requirements/functional/FR-DOC-001.md) - Runs the isolated reviewers and grades findings.
- [FR-SURF-002: Agent-to-agent endpoint](../requirements/functional/FR-SURF-002.md) - Builds the A2UI cards A2A clients receive.
- [FR-TEAM-001: Team customization of behaviour](../requirements/functional/FR-TEAM-001.md) - Applies team instructions and context to the session.
- [FR-TEAM-002: Team resolution and lock](../requirements/functional/FR-TEAM-002.md) - Implements the team lock.
- [NFR-SEC-009: External content is untrusted](../requirements/non-functional/NFR-SEC-009.md) - Builds cards from tool results, never from model output.

# Verification

- `tests/agent`
