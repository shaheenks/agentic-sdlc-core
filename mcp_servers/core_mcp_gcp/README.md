# mcp_servers/core_mcp_gcp

The GCP stack's MCP server (CH-0022). The server itself is `libs/sdlc_mcp`, shared with `core_mcp` (the Entra
stack); this component wires in the Google parts from `sdlc_auth` (CH-0021):

| File | What |
|---|---|
| `server.py` | `build_auth`: Google ID token verifier (audience `SDLC_OAUTH_CLIENT_IDS`, domains from `platform.yaml` `identity.google`, block list by `sub`) with RFC 9728 metadata; `build_identity`: `GoogleAdapter` with `CloudIdentityGroups` (`group_lookup`, `group_cache_seconds`); entry point `sdlc-core-mcp-gcp` |
| `Dockerfile` | image `core-mcp-gcp` (build context: repo root) |

Who the user is: the token's `sub`. What they may do: the config bindings of the Google groups they are in
(only the groups config names are looked up) and `users.yaml` matched by verified email.

Settings:
- `SDLC_OAUTH_CLIENT_IDS` (required, not committed): our OAuth client IDs, comma-separated.
- `platform.yaml` `identity.google` (required): allowed Cloud Identity domains and the group lookup mode.
- Application Default Credentials that may read groups: on GCP the service account `sdlc-<env>-mcp-gcp` with
  the Groups Reader admin role; locally your own ADC with the `cloud-identity.groups.readonly` scope.

Run locally: `docker compose --profile gcp up -d` (port 8090; sign in at http://localhost:4190). Setup:
[docs/guides/GCP_STACK.md](../../docs/guides/GCP_STACK.md).
