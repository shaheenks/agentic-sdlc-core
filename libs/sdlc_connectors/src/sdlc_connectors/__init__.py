"""Talking to external systems (version-01). See libs/sdlc_connectors/README.md.

- http: HttpClient (host allowlist on every request and redirect, retries, per-request
  credentials, never to cross-host redirects)
- storage_format / jira_text: Confluence and Jira rich text -> Markdown
- connections, providers, user_store, service: per-user connections (M6): users' own PATs in a
  per-user secret directory, verified against the provider, used by MCP tools after the policy
  check, never by the model
"""

from sdlc_connectors.errors import ConnectorError

__all__ = ["ConnectorError"]
