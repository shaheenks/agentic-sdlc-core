---
type: Non-Functional Requirement
title: Calls are made as the user
description: Agents forward the user's own token; a service token is never used for user calls.
area: Security
tags:
- requirement
- non-functional
- security
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:30:44+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
---

# Statement

Every call an agent makes for a user shall carry that user's own token.

# Acceptance criteria

- Agents obtain the token with `get_user_token(context)` and forward it to the MCP server.
- `/agui` binds the user id to the token `oid` and strips client-supplied `temp:`, `app:` and `user:` state.
- The chat app forwards only `X-Forwarded-Access-Token` to the agent.
