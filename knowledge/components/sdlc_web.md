---
type: Component
title: sdlc_web
description: 'The agent web app behind oauth2-proxy: user binding, AG-UI, A2A, conversation threads and retention.'
area: Libraries
tags:
- component
- libraries
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../libs/sdlc_web
satisfies:
- /requirements/functional/FR-CONV-001
- /requirements/functional/FR-IDN-001
- /requirements/functional/FR-SURF-001
- /requirements/functional/FR-SURF-002
- /requirements/functional/FR-TEAM-002
- /requirements/non-functional/NFR-OBS-001
- /requirements/non-functional/NFR-PRIV-001
- /requirements/non-functional/NFR-PRIV-002
- /requirements/non-functional/NFR-PRIV-004
- /requirements/non-functional/NFR-SEC-003
- /requirements/non-functional/NFR-SEC-006
- /requirements/non-functional/NFR-SEC-011
verified_by:
- tests/web
sources:
- id: readme
  resource: ../../libs/sdlc_web/README.md
  title: libs/sdlc_web/README.md
---

# Purpose

Serves ADK agents to signed-in users. Its middleware re-validates the token oauth2-proxy forwards and binds every request to the token's `oid`.

Code: `libs/sdlc_web`

# Responsibilities

- `EntraUserBindingMiddleware`: token re-validation, user binding, client state stripping.
- `/agui` (AG-UI) and `/a2a` (A2A 0.3) with a public agent card.
- `/threads`: list and delete the caller's conversations.
- Conversation stores: SQLite with idle retention; Agent Engine sessions on GCP.
- SSE keep-alive; developer tools off unless enabled.

# Depends on

- [sdlc_auth](sdlc_auth.md)
- [user_agent](user_agent.md)

# Requirements

- [FR-CONV-001: Conversation history](../requirements/functional/FR-CONV-001.md) - Lists, replays and deletes the caller's own threads.
- [FR-IDN-001: Sign-in with Entra ID](../requirements/functional/FR-IDN-001.md) - Re-validates the forwarded token on every request.
- [FR-SURF-001: Chat application](../requirements/functional/FR-SURF-001.md) - Serves the AG-UI endpoint the chat uses.
- [FR-SURF-002: Agent-to-agent endpoint](../requirements/functional/FR-SURF-002.md) - Serves `/a2a` and the agent card; checks task and context owners.
- [FR-TEAM-002: Team resolution and lock](../requirements/functional/FR-TEAM-002.md) - Strips client-supplied `sdlc_` state so the lock cannot be forged.
- [NFR-OBS-001: End-to-end tracing](../requirements/non-functional/NFR-OBS-001.md) - Agent side of the end-to-end trace.
- [NFR-PRIV-001: No sensitive values in logs or traces](../requirements/non-functional/NFR-PRIV-001.md) - Agent spans carry no prompts, responses or argument values.
- [NFR-PRIV-002: Hidden resources are not disclosed](../requirements/non-functional/NFR-PRIV-002.md) - Another user's thread answers 404.
- [NFR-PRIV-004: Bounded data retention](../requirements/non-functional/NFR-PRIV-004.md) - Conversation retention.
- [NFR-SEC-003: Strict token validation](../requirements/non-functional/NFR-SEC-003.md) - Re-validates the token and binds the user to its `oid`.
- [NFR-SEC-006: Calls are made as the user](../requirements/non-functional/NFR-SEC-006.md) - Binds the user id to the token and strips client state.
- [NFR-SEC-011: Browser-facing hardening](../requirements/non-functional/NFR-SEC-011.md) - Thread DELETE needs `X-SDLC-Request`; developer tools are off by default.

# Verification

- `tests/web`
