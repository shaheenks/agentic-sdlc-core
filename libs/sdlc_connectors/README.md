# sdlc_connectors

Talking to external systems, shared by ingest (`ingest/loaders`) and the MCP server (version-01).

| Module | What |
|---|---|
| `http.py` | `HttpClient`: host allowlist on every request and redirect, 429/5xx backoff with `Retry-After`, timeouts, credentials from a per-request callable, never sent to a cross-host redirect, one secret re-read after a 401 |
| `storage_format.py`, `jira_text.py` | Confluence storage format, Jira ADF and wiki markup → Markdown |
| `providers.py` | Per provider (GitHub, Bitbucket, Jira, Confluence, Atlassian Cloud; Cloud and Data Center): auth header, token check against the provider's "who am I", read-only calls (`jira_issue`, `confluence_page`, `github_file`, `bitbucket_file`); clients limited to the connection's own host |
| `user_store.py` | Per-user secret directory (one secret per user, `oid` checked on read, key = SHA-256(oid) prefix): `MemoryUserStore` (tests), `FileUserStore` (Fernet, local dev), `GcpUserStore` (Secret Manager `sdlc-<env>-user-<key>`, newest two versions kept) |
| `service.py` | `ConnectionService`: `connect` (verify, expiry required and capped by `max_token_days`), `disconnect`, `status` (never tokens), `credential` for tools (`NotConnected` when missing/expired/rejected; never a service-credential fallback), `mark_invalid`; writes serialised per user |

User connections (version-01 M6), end to end:

1. `config/connections.yaml` (kind `ConnectionCatalog`) lists the systems; `tools.yaml` tools declare
   `credentials: { user: <connection> }`.
2. Users add a personal access token on the chat app's Connections page (`/chat/connections`), which calls the MCP
   server's `/connections/` API through oauth2-proxy. Never through chat.
3. A connected tool runs only after the MCP policy check, then loads the caller's connection and calls the provider
   as the user; provider content is returned as untrusted data.

Configuration (MCP server environment): `SDLC_USER_SECRETS_BACKEND=file` (`SDLC_USER_SECRETS_KEY` Fernet key,
`SDLC_USER_SECRETS_DIR`) | `gcp` (`SDLC_SECRETS_PROJECT`, `SDLC_SECRETS_LOCATION`, `SDLC_ENV`) | unset = off.

Tests: `tests/connectors/`, `tests/mcp/test_connections.py`, `tests/ingest/test_http.py`.
