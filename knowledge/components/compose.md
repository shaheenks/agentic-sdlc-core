---
type: Component
title: compose
description: 'The local stack: Postgres, MCP server, agent, chat app and oauth2-proxy, with tunnel, ingest and observability profiles.'
area: Delivery
tags:
- component
- delivery
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T21:58:37+05:30'
resource: ../../docker-compose.yml
satisfies:
- /requirements/functional/FR-IDN-001
- /requirements/non-functional/NFR-OBS-001
- /requirements/non-functional/NFR-PORT-002
- /requirements/non-functional/NFR-PORT-003
- /requirements/non-functional/NFR-SEC-010
verified_by:
- tests/infra/test_compose.py
---

# Purpose

Runs the whole system on a developer machine, on localhost and through the Cloudflare Tunnel.

Code: `docker-compose.yml`

# Responsibilities

- Services: `postgres`, `core-mcp`, `user-agent`, `ui-copilotkit`, `oauth2-proxy`.
- Profiles: `tunnel` (`oauth2-proxy-public`), `ingest` (`migrate`, `ingest`), `observability` (`jaeger`).
- Explicit environment per service.

# Depends on

- [core_mcp](core_mcp.md)
- [sdlc_web](sdlc_web.md)
- [user_agent](user_agent.md)
- [copilotkit](copilotkit.md)
- [ingest_bootstrap](ingest_bootstrap.md)
- [db](db.md)

# Requirements

- [FR-IDN-001: Sign-in with Entra ID](../requirements/functional/FR-IDN-001.md) - oauth2-proxy signs users in before they reach the app.
- [NFR-OBS-001: End-to-end tracing](../requirements/non-functional/NFR-OBS-001.md) - Jaeger under the observability profile.
- [NFR-PORT-002: Configurable endpoints](../requirements/non-functional/NFR-PORT-002.md) - Runs both the localhost and the tunnel sign-in path.
- [NFR-PORT-003: Local and cloud parity](../requirements/non-functional/NFR-PORT-003.md) - Is the local deployment of the same components.
- [NFR-SEC-010: Least-privilege runtime](../requirements/non-functional/NFR-SEC-010.md) - Agent container gets an explicit environment allow-list; only MCP and ingest get database credentials.

# Verification

- `tests/infra/test_compose.py`
