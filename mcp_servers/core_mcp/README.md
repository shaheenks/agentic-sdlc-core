# mcp_servers/core_mcp

The core MCP server (FastMCP, streamable HTTP at `/mcp`) and the single enforcement point: validates Entra
tokens and the block list, resolves each caller's `EffectivePolicy`, filters `tools/list`, re-authorizes and
rate-limits every `tools/call`, and audits every decision (`sdlc.audit`).

| Module | Tools / routes |
|---|---|
| `server.py` | `ping`, `whoami(explain)`, `list_skills`, `load_skill` (hidden skills answer "unknown skill"); wiring, auth, policy, rate limits |
| `identity.py` | The caller of each request: validated token → `Principal` → `EffectivePolicy` (one config snapshot per request) |
| `team_tools.py` | `get_agent_context(team=)` (team instructions, context, teams, default team, document-flow defaults), `resolve_team(hints)` |
| `knowledge_tools.py` | `search_knowledge` (vector + keyword), `graph_query` (vector + keyword seeds + graph walk), under RLS |
| `artifact_tools.py`, `artifacts_api.py` | `save/list/read/delete_artifact` (owner only, versions); HTTP `/artifacts/` (list, download, versions, DELETE) |
| `connected_tools.py`, `connections_api.py` | `jira_get_issue`, `confluence_get_page`, `github_get_file`, `bitbucket_get_file` with the user's own PAT; HTTP `/connections/` |
| `admin_tools.py` | `config_info`, `config_explain` (admin only) |
| `audit.py`, `auth_audit.py`, `correlation.py`, `telemetry.py` | Audit records, `auth_failure`, request / conversation ids, OpenTelemetry |
| `reconcile_cli.py` | `sdlc-reconcile-connections [--apply]` |

Access to every tool is declared in `config/` (`tools.yaml`, `roles.yaml`, `teams/`), never here.
