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

import os
import threading
import time
from collections.abc import Callable
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


# Correlation (tracking only): the ADK conversation id travels with each MCP call so the server
# can tag audit records. Client-supplied, so the server records it as correlation data and never
# uses it for decisions. One MCP session is pooled per (token, conversation).
AGENT_SESSION_HEADER = "X-SDLC-Agent-Session"


# Nested agent runs (Goldfish reviewers, version-03 P10) have their own throwaway sessions; the
# tool that starts them binds the parent conversation id here, so their MCP calls are audited
# under the user's conversation.
_conversation_id: ContextVar[str | None] = ContextVar("sdlc_conversation_id", default=None)


def set_conversation_id(conversation_id: str | None) -> Token:
    """Use `conversation_id` as the agent session id in this context. Pair with reset."""
    return _conversation_id.set(conversation_id)


def reset_conversation_id(reset_token: Token) -> None:
    _conversation_id.reset(reset_token)


def agent_session_id(context: Any = None) -> str | None:
    bound = _conversation_id.get()
    if bound:
        return bound
    session = getattr(context, "session", None)
    session_id = getattr(session, "id", None)
    return str(session_id) if session_id else None


# GCP-native hosting (CH-0014, design D17 N5): the MCP server can sit behind Cloud Run invoker IAM.
# Cloud Run then checks a Google ID token for this workload in X-Serverless-Authorization, so the
# user's Entra token keeps `Authorization` and the MCP server reads only that. Off unless
# SDLC_MCP_IAM_AUDIENCE (the MCP service URL) is set: local compose and dev send nothing extra.
IAM_HEADER = "X-Serverless-Authorization"
IAM_AUDIENCE_ENV = "SDLC_MCP_IAM_AUDIENCE"
_ID_TOKEN_TTL = 45 * 60  # Google ID tokens live 60 minutes; refresh well before


class _IdTokenCache:
    """One Google ID token per audience for this process, refreshed before it expires. The token
    is the agent's own identity (ADC: Agent Identity on Agent Runtime), never the user's."""

    def __init__(self, fetch: Callable[[str], str] | None = None):
        self._fetch = fetch or _fetch_id_token
        self._tokens: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def get(self, audience: str) -> str:
        with self._lock:
            token, fetched = self._tokens.get(audience, ("", 0.0))
            if not token or time.monotonic() - fetched > _ID_TOKEN_TTL:
                token = self._fetch(audience)
                self._tokens[audience] = (token, time.monotonic())
            return token


def _fetch_id_token(audience: str) -> str:
    from google.auth.transport.requests import Request  # only where the IAM header is enabled
    from google.oauth2 import id_token

    return id_token.fetch_id_token(Request(), audience)


_id_tokens = _IdTokenCache()


def agent_header_provider(context: Any = None) -> dict[str, str]:
    """ADK McpToolset `header_provider`: the user's token plus the conversation id, and (when
    SDLC_MCP_IAM_AUDIENCE is set) the agent's Google ID token for Cloud Run IAM. Nothing at all
    without a user token: the agent never calls the MCP server on its own behalf."""
    headers = bearer_header_provider(context)
    if not headers:
        return headers
    session_id = agent_session_id(context)
    if session_id:
        headers[AGENT_SESSION_HEADER] = session_id
    audience = os.environ.get(IAM_AUDIENCE_ENV, "")
    if audience:
        headers[IAM_HEADER] = f"Bearer {_id_tokens.get(audience)}"
    return headers
