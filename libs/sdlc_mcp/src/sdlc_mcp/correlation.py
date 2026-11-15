"""Correlation IDs for audit records (tracking only, never used for decisions).

- agent_session_id: the ADK conversation, sent by the agent as `X-SDLC-Agent-Session`
                    (client-supplied: recorded as-is when well-formed). This is the stable key
                    for following one conversation across requests.
- mcp_session_id:   the `Mcp-Session-Id` header, recorded only when a client sends it (older MCP
                    protocol versions). Current protocol versions are stateless on the server:
                    no header is sent and fastmcp's per-request session id changes every request,
                    so it would only duplicate request_id.
Values that are not short, safe identifiers are recorded as "invalid" (no log injection).
"""

import re
from collections.abc import Mapping

from fastmcp.server.dependencies import get_http_headers

AGENT_SESSION_HEADER = "x-sdlc-agent-session"
MCP_SESSION_HEADER = "mcp-session-id"
_SAFE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _clean(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return value if _SAFE.match(value) else "invalid"


def correlation_ids(headers: Mapping[str, str]) -> dict[str, str | None]:
    lowered = {k.lower(): v for k, v in headers.items()}
    return {
        "mcp_session_id": _clean(lowered.get(MCP_SESSION_HEADER)),
        "agent_session_id": _clean(lowered.get(AGENT_SESSION_HEADER)),
    }


def current_correlation() -> dict[str, str | None]:
    """Correlation IDs of the current MCP request (None outside HTTP / when not sent)."""
    return correlation_ids(get_http_headers(include_all=True))
