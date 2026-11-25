"""Who user_agent calls user_agent_mcp for (DEC-0010).

The session's user travels as `X-SDLC-User-Id` (the session's user ID, the Google account ID sdlc_ui verified)
and `X-SDLC-User-Email` (from state sdlc_ui set when it created the session). The runtime proves who it is with
its own service account's Google ID token, minted for user_agent_mcp. A session without both is sent without
them, and user_agent_mcp refuses it (fail closed)."""

import os
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any

EMAIL_KEY = "sdlc_user_email"  # set by sdlc_ui when it creates the session; nothing else writes it
TEAM_KEY = "sdlc_team"  # the team a run is for; absent in chat
TITLE_KEY = "sdlc_title"
SURFACE = "user_agent"
TOKEN_LIFETIME = 45 * 60  # Google ID tokens last an hour; refresh well before


class IdTokens:
    """This runtime's Google ID token for one audience, from the metadata server, cached."""

    def __init__(self, audience: str, fetch: Callable[[str], str] | None = None) -> None:
        self.audience = audience
        self._fetch = fetch or _fetch_id_token
        self._lock = threading.Lock()
        self._token: tuple[str, float] | None = None

    def get(self) -> str:
        with self._lock:
            if self._token is None or self._token[1] <= time.time():
                self._token = (self._fetch(self.audience), time.time() + TOKEN_LIFETIME)
            return self._token[0]


def _fetch_id_token(audience: str) -> str:
    import google.auth.transport.requests
    import google.oauth2.id_token

    return google.oauth2.id_token.fetch_id_token(google.auth.transport.requests.Request(), audience)


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
