---
type: Component
title: core_mcp
description: 'The MCP server: the single point that authenticates, filters, authorizes, rate-limits and audits every call.'
area: Services
tags:
- component
- services
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../mcp_servers/core_mcp
satisfies:
- /requirements/functional/FR-ART-001
- /requirements/functional/FR-ART-002
- /requirements/functional/FR-ART-003
- /requirements/functional/FR-AUTHZ-001
- /requirements/functional/FR-AUTHZ-002
- /requirements/functional/FR-AUTHZ-004
- /requirements/functional/FR-AUTHZ-006
- /requirements/functional/FR-CFG-004
- /requirements/functional/FR-CONN-001
- /requirements/functional/FR-CONN-002
- /requirements/functional/FR-CONN-003
- /requirements/functional/FR-DOC-001
- /requirements/functional/FR-IDN-001
- /requirements/functional/FR-IDN-003
- /requirements/functional/FR-IDN-004
- /requirements/functional/FR-KNOW-002
- /requirements/functional/FR-KNOW-003
- /requirements/functional/FR-SKILL-001
- /requirements/functional/FR-SURF-003
- /requirements/functional/FR-TEAM-001
- /requirements/functional/FR-TEAM-002
- /requirements/non-functional/NFR-AUD-001
- /requirements/non-functional/NFR-AUD-002
- /requirements/non-functional/NFR-OBS-001
- /requirements/non-functional/NFR-PRIV-001
- /requirements/non-functional/NFR-PRIV-002
- /requirements/non-functional/NFR-PRIV-004
- /requirements/non-functional/NFR-REL-002
- /requirements/non-functional/NFR-SEC-001
- /requirements/non-functional/NFR-SEC-004
- /requirements/non-functional/NFR-SEC-009
- /requirements/non-functional/NFR-SEC-011
verified_by:
- tests/mcp
- tests/policy/test_matrix.py
- tests/policy/test_rate_limits.py
sources:
- id: readme
  resource: ../../mcp_servers/core_mcp/README.md
  title: mcp_servers/core_mcp/README.md
---

# Purpose

Serves tools, skills and knowledge over streamable HTTP. Its policy middleware resolves the caller once per request against one config snapshot, then filters listings and authorizes each call before any tool runs. It also serves the `/connections/` and `/artifacts/` browser APIs under the same checks.

Code: `mcp_servers/core_mcp`

# Responsibilities

- Token validation and block-list check on every request; rejected requests are audited by `auth_audit`.
- Policy middleware (`audit.py`): `tools/list` filtering, per-call authorization with argument limits, rate limits, audit records.
- Tools: identity (`ping`, `whoami`), skills, team context, knowledge search and graph, artifacts, connected tools and admin tools.
- HTTP APIs: `/connections/` and `/artifacts/`.
- `sdlc-reconcile-connections` CLI.
- OpenTelemetry tracing and correlation ids.

# Depends on

- [sdlc_auth](sdlc_auth.md)
- [sdlc_config](sdlc_config.md)
- [sdlc_policy](sdlc_policy.md)
- [sdlc_db](sdlc_db.md)
- [sdlc_connectors](sdlc_connectors.md)
- [sdlc_artifacts](sdlc_artifacts.md)
- [sdlc_secrets](sdlc_secrets.md)

# Requirements

- [FR-ART-001: Save and manage artifacts](../requirements/functional/FR-ART-001.md) - `save/list/read/delete_artifact`, owner taken from the token.
- [FR-ART-002: Artifact versions](../requirements/functional/FR-ART-002.md) - `replaces` / `base_version` handling.
- [FR-ART-003: Download and review artifacts in the chat](../requirements/functional/FR-ART-003.md) - `/artifacts/` download API and numbered reads.
- [FR-AUTHZ-001: Selective disclosure of tools](../requirements/functional/FR-AUTHZ-001.md) - Filters `tools/list` and audits `tools_list`.
- [FR-AUTHZ-002: Per-call authorization with argument limits](../requirements/functional/FR-AUTHZ-002.md) - Re-authorizes every `tools/call` including arguments.
- [FR-AUTHZ-004: Per-user rate limits](../requirements/functional/FR-AUTHZ-004.md) - Applies the rate limiter after authorization and audits `rate_limited`.
- [FR-AUTHZ-006: Team roles are scoped to their team](../requirements/functional/FR-AUTHZ-006.md) - `whoami(explain)`, `config_explain` and audit records show scoped roles (`approver@payments`).
- [FR-CFG-004: Admin view of the running configuration](../requirements/functional/FR-CFG-004.md) - `config_info` admin tool.
- [FR-CONN-001: Users connect their own accounts](../requirements/functional/FR-CONN-001.md) - `/connections/` API.
- [FR-CONN-002: Tools act as the user](../requirements/functional/FR-CONN-002.md) - Connected tools load the caller's connection after the policy check.
- [FR-CONN-003: Atlassian and Data Center connections](../requirements/functional/FR-CONN-003.md) - `jira_get_issue` and `confluence_get_page` with the caller's `atlassian` connection.
- [FR-DOC-001: Reviewed document flow](../requirements/functional/FR-DOC-001.md) - Saves the finished document and its review as artifacts.
- [FR-IDN-001: Sign-in with Entra ID](../requirements/functional/FR-IDN-001.md) - Answers 401 without a valid token, audits `auth_failure`, serves `whoami`.
- [FR-IDN-003: Users can see their own access](../requirements/functional/FR-IDN-003.md) - `whoami(explain)` for the caller; `config_explain` for admins.
- [FR-IDN-004: Revocation of access](../requirements/functional/FR-IDN-004.md) - Refuses blocked users; hosts the reconcile CLI.
- [FR-KNOW-002: Knowledge search with citations](../requirements/functional/FR-KNOW-002.md) - `search_knowledge` tool.
- [FR-KNOW-003: Knowledge graph queries](../requirements/functional/FR-KNOW-003.md) - `graph_query` tool.
- [FR-SKILL-001: Skills served per user](../requirements/functional/FR-SKILL-001.md) - `list_skills` and `load_skill`; hidden skills answer 'unknown skill'.
- [FR-SURF-003: Direct MCP clients](../requirements/functional/FR-SURF-003.md) - Streamable HTTP endpoint for direct MCP clients.
- [FR-TEAM-001: Team customization of behaviour](../requirements/functional/FR-TEAM-001.md) - `get_agent_context` serves team instructions, context and flow defaults.
- [FR-TEAM-002: Team resolution and lock](../requirements/functional/FR-TEAM-002.md) - `resolve_team` and the membership check behind the team lock.
- [NFR-AUD-001: Every decision is audited](../requirements/non-functional/NFR-AUD-001.md) - Writes every audit event to `sdlc.audit`.
- [NFR-AUD-002: Records can be correlated](../requirements/non-functional/NFR-AUD-002.md) - Adds `request_id`, `agent_session_id`, `trace_id` and `config_version`.
- [NFR-OBS-001: End-to-end tracing](../requirements/non-functional/NFR-OBS-001.md) - Emits MCP and database spans; reads trace context from MCP `_meta`.
- [NFR-PRIV-001: No sensitive values in logs or traces](../requirements/non-functional/NFR-PRIV-001.md) - Audit carries an argument hash; spans carry no values.
- [NFR-PRIV-002: Hidden resources are not disclosed](../requirements/non-functional/NFR-PRIV-002.md) - Hidden skills, teams and other users' artifacts answer as if absent.
- [NFR-PRIV-004: Bounded data retention](../requirements/non-functional/NFR-PRIV-004.md) - Applies the artifact retention setting.
- [NFR-REL-002: Stable MCP sessions](../requirements/non-functional/NFR-REL-002.md) - Holds no session state.
- [NFR-SEC-001: Single enforcement point](../requirements/non-functional/NFR-SEC-001.md) - Is the enforcement point.
- [NFR-SEC-004: Fail closed](../requirements/non-functional/NFR-SEC-004.md) - Refuses to start without valid config and Entra IDs.
- [NFR-SEC-009: External content is untrusted](../requirements/non-functional/NFR-SEC-009.md) - Treats provider content from connected tools as untrusted data.
- [NFR-SEC-011: Browser-facing hardening](../requirements/non-functional/NFR-SEC-011.md) - Attachment downloads with `nosniff` and CSP sandbox; DELETE needs `X-SDLC-Request`.

# Verification

- `tests/mcp`
- `tests/policy/test_matrix.py`
- `tests/policy/test_rate_limits.py`
