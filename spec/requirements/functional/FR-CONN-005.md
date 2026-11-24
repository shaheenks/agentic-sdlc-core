---
type: Functional Requirement
title: "Secrets never pass through agents"
description: "Personal access tokens are entered outside the conversation and never reach a model, an agent or a tool result."
tags: [requirement, connections]
status: draft
x-area: CONN
x-priority: must
x-implementation: planned
---

# Statement

The system shall collect a user's personal access token or other connection secret only through a secure page
outside the conversation, and never pass it to or return it from a model, an agent or a tool.

# Acceptance criteria

- No tool has a parameter for a secret value, and no tool result contains one.
- To save or replace a PAT, the agent calls a tool that returns a link to the secure entry page: by MCP
  URL-mode elicitation where the client supports it, or as a link to the sdlc_ui Connections page.
- The entry page belongs to the platform, requires the same signed-in user, and stores the secret directly in
  the secrets store.
- After saving, the agent can see only the connection's status (connected, expired, failed test) and metadata
  (provider, account name, scopes where the provider reports them, expiry).

# Notes

A secret typed into a chat would reach the model, its transcripts and the model provider's logs, against
[NFR-PRIV-001](../non-functional/NFR-PRIV-001.md) and [NFR-SEC-004](../non-functional/NFR-SEC-004.md).

# Citations

[1] [MCP specification: elicitation](https://modelcontextprotocol.io/specification/latest/client/elicitation)
