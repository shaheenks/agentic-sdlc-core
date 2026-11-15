---
type: Non-Functional Requirement
title: Calls are made as the user
description: Agents forward the user's own token; a service token is never used for user calls.
area: Security
tags:
- requirement
- non-functional
- security
status: draft
priority: must
implementation: live
sources:
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

Every call an agent makes for a user shall carry that user's own token.

# Acceptance criteria

- Agents obtain the token with `get_user_token(context)` and forward it to the MCP server.
- `/agui` binds the user id to the token `oid` and strips client-supplied `temp:`, `app:` and `user:` state.
- The chat app forwards only `X-Forwarded-Access-Token` to the agent.
- On the GCP stack the forwarded token is the user's Google ID token, and the agent's session user is its `sub`.

# Notes

Edited by CH-0022: the GCP stack's user token.
