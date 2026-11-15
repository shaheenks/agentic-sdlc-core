# sdlc_mcp

The SDLC MCP server body, shared by the MCP server components (CH-0020): tools (skills, team context,
knowledge, connected sources, artifacts, admin), the policy middleware (RBAC on `tools/list` and
`tools/call`, rate limits), audit, the Connections and Artifacts HTTP APIs, tracing and the
`sdlc-reconcile-connections` CLI.

It knows nothing about the identity provider. A server component passes:
- an `AuthProvider` (fastmcp) that verifies tokens, and
- an `IdentityAdapter` (`sdlc_mcp.identity`) that turns verified claims into a `Principal`, its
  memberships (`app_role:` / `group:` keys, possibly looked up asynchronously), its `users.yaml` entry, its
  `whoami` view and the reason a rejected token was refused.

`mcp_servers/core_mcp` is the Entra component (`sdlc_core_mcp.entra.EntraAdapter`); the GCP stack's adapter is
`sdlc_auth.google.GoogleAdapter` (CH-0021).

| Module | Tools / routes |
|---|---|
| `server.py` | `build_server`, `build_http_app`, `serve`; `ping`, `whoami(explain)`, `list_skills`, `load_skill` (hidden skills answer "unknown skill"); wiring, policy, rate limits |
| `identity.py` | The `IdentityAdapter` port; the caller of each request: validated token → `Principal` → `EffectivePolicy` (one config snapshot per request) |
| `team_tools.py` | `get_agent_context(team=)` (team instructions, context, teams, default team, document-flow defaults), `resolve_team(hints)` |
| `knowledge_tools.py` | `search_knowledge` (vector + keyword), `graph_query` (vector + keyword seeds + graph walk), under RLS |
| `artifact_tools.py`, `artifacts_api.py` | `save/list/read/delete_artifact` (owner only, versions); HTTP `/artifacts/` (list, download, versions, DELETE) |
| `connected_tools.py`, `connections_api.py` | `jira_get_issue`, `confluence_get_page`, `github_get_file`, `bitbucket_get_file` with the user's own PAT; HTTP `/connections/` |
| `admin_tools.py` | `config_info`, `config_explain` (admin only) |
| `audit.py`, `auth_audit.py`, `correlation.py`, `telemetry.py` | Audit records, `auth_failure`, request / conversation ids, OpenTelemetry |
| `reconcile_cli.py` | `sdlc-reconcile-connections [--apply]` |

Concept: [knowledge/components/sdlc_mcp.md](../../knowledge/components/sdlc_mcp.md).
