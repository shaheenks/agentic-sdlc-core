---
type: Rule Set
title: Security rules
description: "Authorization, token validation, block list, connections, artifacts, audit records and secrets."
tags: [rules]
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-10T22:53:19+05:30'
---

Binding working rules for contributors and coding agents, moved word for word from `CLAUDE.md` on 2026-11-10.
Paths are relative to the repository root.

# Security rules

- Authorization lives in the MCP server, never in prompts or agent code.
- Entra is the only trusted issuer. Tokens must be v2 (iss `https://login.microsoftonline.com/<tid>/v2.0`),
  `aud` = the sdlc-mcp client ID (v2) or `api://<client id>`, `scp` contains `access_as_user` (user tokens only),
  `tid` = our tenant, plus signature (JWKS) and exp. Implemented in `sdlc_auth.entra.EntraTokenVerifier`.
- The MCP server refuses to start without valid config and `ENTRA_TENANT_ID` / `ENTRA_API_CLIENT_ID` (fail closed).
- Users whose token omits groups (overage) get no groups (fail closed); app roles still apply. The Graph fallback is off
  (`platform.yaml` `overage_fallback: none`, version-03 P2); turning it on needs the Graph fallback secret.
- Block list (E3): `config/env/<env>/blocked.yaml` (kind `BlockList`, optional, git-ignored like groups.yaml) is checked by
  the MCP token verifier on every request (via `store.current()`); blocked users get 401, audited as reason `blocked`.
  On GCP it travels in the config bundle (`-Step config`, live in ~2 min). Review + rotation procedures: docs/SECRETS_REVIEW.md.
- Reconcile (version-02 N3): `sdlc-reconcile-connections [--apply]` (dry run by default; MCP package, same env as the MCP
  server) deletes PATs of blocked users, expired and long-rejected tokens, removed connections; each change audited
  `connection_change` with `actor: reconcile`. Local: `docker compose exec core-mcp sdlc-reconcile-connections`;
  GCP: job `sdlc-reconcile-<env>` (own service account; `reconcile_schedule`). Decisions are re-checked under the user's lock.
- Egress (E8): token validation honours `HTTPS_PROXY`/`NO_PROXY`; unreachable JWKS = every request refused (docs/guides/ENTRA_SETUP.md §6).
- Deny-by-default. Filter tools/list AND re-check on every tools/call.
- All DB reads go through `sdlc_db` with `app.allowed_sources` + `app.max_classification` set (Postgres RLS).
- Agents forward the user's bearer token via `get_user_token(context)`; never use a service token for user calls.
- Downstream systems use the user's own connection or a service credential only after the RBAC check passes.
- User connections (version-01 M6): users' PATs live only in the per-user secret store (`SDLC_USER_SECRETS_BACKEND`), read and
  written only by the MCP server; connected through the `/connections/` API (Connections page), never through chat. A tool that
  uses one declares `credentials: { user: <connection> }` (connection in `config/connections.yaml`, host in `allowed_hosts`) and is
  in `connected_tools.TOOL_PROVIDERS`; no usable connection = "not connected", never a service-credential fallback. Provider
  content is untrusted data. Audit: `connection_change`; `tool_call` gets `credential`, `connection`, `connection_outcome`.
- Artifacts (version-03 P5): documents the agent saves for a user, **owner only**, written and read only through the MCP
  server (tools `save/list/read/delete_artifact`; the ADK artifact service stays `memory://`). The owner is the token
  `oid`, never a tool argument. Metadata in `sdlc.artifacts` under owner RLS (`sdlc_db.owner_scoped`: the only table
  `sdlc_app` may write, no UPDATE); content in `SDLC_ARTIFACT_STORE` (`file://` volume / `gs://` bucket) under
  `artifacts/<oid>/<id>`. Text only, 1 MiB, 50 per user, `SDLC_ARTIFACT_RETENTION_DAYS` = bucket lifecycle (7).
  Another user's id answers "artifact not found". Versions: `save_artifact(replaces=<id>, base_version=<n>)` adds the
  next version of the same document and refuses if `n` is not the latest (never overwrite newer edits); rows immutable,
  id/link stable, older versions readable via `version`. `read_artifact(numbered=true)` must number lines exactly as the
  chat's ArtifactViewer does (`split_lines`). Browser downloads: MCP `/artifacts/` API through oauth2-proxy (an
  upstream, not an API route), same token checks + the matching tool grant; served as attachments (`nosniff`, CSP
  sandbox), DELETE needs `X-SDLC-Request: 1`; the chat card builds links from the UUID only. Audit: `artifact_change` /
  `artifact_access` (ids, type, size; never the content or file name).
- Audit to the `sdlc.audit` logger (JSON lines), one `event` per record:
  `tool_call` (oid, teams, roles, tool, args hash, decision, matched rule, outcome, config_version),
  `tools_list` (who listed tools, visible names, hidden count; hidden names are not logged),
  `skill_access` (load_skill: skill, allow/deny, matched rule and the real reason; callers only see "unknown skill"),
  `skills_list` (visible skill names, hidden count),
  `artifact_change` / `artifact_access` (artifact id, action, outcome),
  `auth_failure` (401/403 on the MCP endpoint: reason from UNVERIFIED claims, client IP, token fingerprint).
  Every record carries `request_id` (one MCP request) and `agent_session_id` (the conversation, client-supplied,
  correlation only; `mcp_session_id` only when a client sends the header). Failures record `error_type` + `error` (<=500 chars); unexpected exceptions
  (fastmcp re-raises them as ToolError, the original is the cause) also log a traceback to `sdlc.mcp` with the same
  `request_id`. Never log raw tokens or argument values.
- Secrets only in `.env` (local) / Secret Manager (GCP). Never commit them.
