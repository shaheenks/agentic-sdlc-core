---
type: Non-Functional Requirement
title: Stable MCP sessions
description: There is one MCP client session per user and conversation, and the server holds no session state.
area: Reliability
tags:
- requirement
- non-functional
- reliability
status: stable
priority: should
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:45:18+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
---

# Statement

An agent shall use one MCP client session per user token and conversation, and the MCP server shall hold no session state.

# Acceptance criteria

- Session headers carry only the user token and the conversation id.
- No per-turn value is ever added as a header.
