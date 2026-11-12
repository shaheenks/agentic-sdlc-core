---
type: Component
title: sdlc_connectors
description: 'Talking to external systems: allowlisted HTTP, provider adapters, per-user secret store, the connection service and reconcile.'
area: Libraries
tags:
- component
- libraries
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../libs/sdlc_connectors
satisfies:
- /requirements/functional/FR-CONN-001
- /requirements/functional/FR-CONN-002
- /requirements/functional/FR-CONN-003
- /requirements/functional/FR-IDN-004
- /requirements/functional/FR-KNOW-001
- /requirements/functional/FR-KNOW-006
- /requirements/non-functional/NFR-SEC-008
verified_by:
- tests/connectors
- tests/ingest/test_http.py
- tests/mcp/test_connections.py
sources:
- id: readme
  resource: ../../libs/sdlc_connectors/README.md
  title: libs/sdlc_connectors/README.md
---

# Purpose

Everything that reaches GitHub, Bitbucket, Jira or Confluence goes through here, for both ingest loaders and MCP tools.

Code: `libs/sdlc_connectors`

# Responsibilities

- `HttpClient`: host allowlist on every request and redirect, timeouts, retries.
- Provider adapters per system and edition (Cloud, Data Center).
- Per-user secret store and the connection service (connect, disconnect, status).
- Reconcile of stored connections.
- Jira and Confluence content to Markdown.

# Depends on

- [sdlc_secrets](sdlc_secrets.md)
- [sdlc_config](sdlc_config.md)

# Requirements

- [FR-CONN-001: Users connect their own accounts](../requirements/functional/FR-CONN-001.md) - Stores, verifies and removes users' connections.
- [FR-CONN-002: Tools act as the user](../requirements/functional/FR-CONN-002.md) - Calls providers with the user's own credential.
- [FR-CONN-003: Atlassian and Data Center connections](../requirements/functional/FR-CONN-003.md) - Atlassian and Data Center providers, with the account check before a connection is saved.
- [FR-IDN-004: Revocation of access](../requirements/functional/FR-IDN-004.md) - Reconcile removes credentials of blocked users and stale tokens.
- [FR-KNOW-001: Ingest declared sources](../requirements/functional/FR-KNOW-001.md) - Gives loaders their HTTP client and content converters.
- [FR-KNOW-006: Atlassian and Bitbucket sources](../requirements/functional/FR-KNOW-006.md) - HTTP client and the Jira and Confluence content converters used by the Atlassian loaders.
- [NFR-SEC-008: Controlled egress](../requirements/non-functional/NFR-SEC-008.md) - Enforces the host allowlist on every request and redirect.

# Verification

- `tests/connectors`
- `tests/ingest/test_http.py`
- `tests/mcp/test_connections.py`
