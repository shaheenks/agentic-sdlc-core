"""Who user_agent calls user_agent_mcp for (DEC-0010).

The session's user travels as `X-SDLC-User-Id` (the session's user ID, the Google account ID sdlc_ui verified)
and `X-SDLC-User-Email` (from state sdlc_ui set when it created the session). The runtime proves who it is with
its own service account's Google ID token, minted for user_agent_mcp. A session without both is sent without
them, and user_agent_mcp refuses it (fail closed)."""

import os
from collections.abc import Callable, Mapping
from typing import Any

from sdlc_adk import IdTokens

EMAIL_KEY = "sdlc_user_email"  # set by sdlc_ui when it creates the session; nothing else writes it
TEAM_KEY = "sdlc_team"  # the team a run is for; absent in chat
TITLE_KEY = "sdlc_title"
SURFACE = "user_agent"

__all__ = ["IdTokens", "header_provider", "mcp_headers", "tokens_from_env"]


def mcp_headers(user_id: str | None, state: Mapping[str, Any], tokens: IdTokens | None) -> dict[str, str]:
    """The headers of one call to user_agent_mcp; none at all without a user."""
    email = state.get(EMAIL_KEY)
    if not user_id or not isinstance(email, str) or not email:
        return {}
    headers = {"X-SDLC-User-Id": user_id, "X-SDLC-User-Email": email, "X-SDLC-Surface": SURFACE}
    team = state.get(TEAM_KEY)
    if isinstance(team, str) and team:
        headers["X-SDLC-Team"] = team
    if tokens is not None:
        headers["Authorization"] = f"Bearer {tokens.get()}"
    return headers


def header_provider(tokens: IdTokens | None) -> Callable[[Any], dict[str, str]]:
    def provide(ctx) -> dict[str, str]:
        return mcp_headers(ctx.user_id, ctx.state, tokens)

    return provide


def tokens_from_env(mcp_url: str, environ: Mapping[str, str] | None = None) -> IdTokens | None:
    """`SDLC_CALLER_AUTH=id_token` (default) proves the runtime with its ID token; `none` sends no proof and
    works only against a user_agent_mcp in the local environment (identity mode trusted_header)."""
    e = os.environ if environ is None else environ
    auth = e.get("SDLC_CALLER_AUTH", "id_token")
    if auth == "none":
        return None
    if auth != "id_token":
        raise ValueError("SDLC_CALLER_AUTH must be id_token or none")
    return IdTokens(e.get("SDLC_MCP_AUDIENCE") or mcp_url)
