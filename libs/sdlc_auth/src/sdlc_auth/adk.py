"""User-token passthrough for ADK agents (Stage 2d).

Each surface puts the signed-in user's Entra access token where `get_user_token` finds it:
  - adk web behind oauth2-proxy: sdlc_web's middleware validates the token and sets it in a
    request-scoped ContextVar. ADK runs the agent in a task created inside the request, which
    inherits the ContextVar, so the token is never written to session storage.
  - surfaces that deliver the token via session state (Gemini Enterprise, Stage 8):
    USER_TOKEN_STATE_KEY.
Agents never substitute a service token: with no user token, no Authorization header is sent
and the MCP server answers 401 (fail closed).
"""

from contextvars import ContextVar, Token
from typing import Any

# `temp:` state is scoped to one invocation and not persisted by ADK session services.
USER_TOKEN_STATE_KEY = "temp:sdlc_user_access_token"  # noqa: S105 (a key name, not a secret)

_request_token: ContextVar[str | None] = ContextVar("sdlc_user_access_token", default=None)


def set_request_token(token: str | None) -> Token:
    """Bind the user's token to the current request context. Pair with reset_request_token."""
    return _request_token.set(token)


def reset_request_token(reset_token: Token) -> None:
    _request_token.reset(reset_token)


def get_user_token(context: Any = None) -> str | None:
    """The current user's Entra access token, or None. `context` is an ADK ReadonlyContext."""
    token = _request_token.get()
    if token:
        return token
    state = getattr(context, "state", None)
    if state is not None:
        value = state.get(USER_TOKEN_STATE_KEY)
        if isinstance(value, str) and value:
            return value
    return None


def bearer_header_provider(context: Any = None) -> dict[str, str]:
    """ADK McpToolset `header_provider`: forward the user's token to the MCP server."""
    token = get_user_token(context)
    return {"Authorization": f"Bearer {token}"} if token else {}
