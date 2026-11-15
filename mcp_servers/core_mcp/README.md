# mcp_servers/core_mcp

The MCP server of the Entra stack. The server body (FastMCP, streamable HTTP at `/mcp`, the single
enforcement point: policy, RBAC, rate limits, audit, tools, `/connections/` and `/artifacts/`) is the shared
library [`libs/sdlc_mcp`](../../libs/sdlc_mcp/README.md) (CH-0020). This component adds only the Entra parts:

| Module | What |
|---|---|
| `server.py` | Entra token verifier and block list, OAuth protected-resource metadata, the `sdlc-core-mcp` entry point |
| `entra.py` | `EntraAdapter`: user = `oid`, memberships = app roles (`app_role:` keys), `users.yaml` by `oid`, `whoami` view, why a rejected Entra token was refused |

Access to every tool is declared in `config/` (`tools.yaml`, `roles.yaml`, `teams/`), never here.
