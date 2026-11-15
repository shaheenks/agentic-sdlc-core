---
type: Non-Functional Requirement
title: Least-privilege runtime
description: Each service gets only the credentials and environment it needs.
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

Each service shall run with only the credentials, environment and database rights it needs.

# Acceptance criteria

- Only MCP servers and ingest get database credentials.
- Agent containers get an explicit environment allow-list, never the whole `.env`.
- Database roles are separated: `sdlc_owner` (migrations), `sdlc_app` (read-only except its own artifact rows) and `sdlc_ingest` (writes).
- On GCP-native hosting, the MCP server accepts calls only from allowed Google identities (Cloud Run invoker IAM); per-user access is decided by the user's own token (on the GCP stack, the Google ID token).
- The GCP stack's MCP server runs as its own service account, the only one allowed to read the Cloud Identity Groups API.

# Notes

Edited by CH-0013: invoker IAM on the native MCP service (design D17).

Edited by CH-0022: the GCP stack's own token and service account.
