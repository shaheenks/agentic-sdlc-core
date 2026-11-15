"""The user agent on Agent Runtime (GCP-native hosting, design D17, CH-0014).

`adk web` + `sdlc_web` serve the agent locally and on GCP dev. On Agent Runtime there is no web
layer of ours, so this app is the entry point and runs the same checks first
(`sdlc_agent.runtime_guard`):
- every call carries the user's token, which is re-validated (fail closed): on the GCP stack a
  Google ID token (`SDLC_IDENTITY_PROVIDER=google`, set by deploy_agent_runtime.py; CH-0022), else
  the Entra access token;
- the ADK user id is the token's user id (Google `sub`, Entra `oid`); a caller can never pick
  another user's id or session;
- client state is cleaned (no tokens, `temp:`, `app:`, `user:` or `sdlc_` keys);
- the token is bound for this call only (`sdlc_auth.adk.set_request_token`), so the agent's MCP
  calls carry it, and it is never written to the session.

Operations (`register_operations`):
- `stream_query(message, user_token, session_id=None, state=None)`: async stream of ADK events
  (JSON), the first being `{"session": <id>}` so a client can continue the conversation;
- `list_threads(user_token)`: the caller's conversations, newest first (id, title, updatedAt);
- `delete_thread(user_token, session_id)`: deletes one of the caller's conversations.

A refusal is a result, never an exception: `{"error": {"code", "message"}}` (for `stream_query`, a
single event), with code `unauthenticated`, `not_found`, `invalid_argument` or `internal` (CH-0019).

The Agent Runtime caller (the UI service account) is trusted to reach the engine, never to speak
for a user: who the user is comes only from the token.
"""

import logging
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sdlc_agent.runtime_guard import NotAuthenticated, clean_state, verify_user
from sdlc_auth.adk import reset_request_token, set_request_token

log = logging.getLogger(__name__)

TITLE_STATE_KEY = "sdlc_title"  # server-owned: set from the first message, never by a client
TITLE_CHARS = 80
MAX_THREADS = 30
MAX_MESSAGE_CHARS = 32_000


class UserAgentApp:
    """Agent Runtime app around `agents/user_agent/agent.py`'s `root_agent`.

    The constructor takes only plain values (the app is pickled at deploy time); `set_up` builds
    the runner on the server. Tests pass `verifier`, `agent` and `session_service` directly."""

    def __init__(
        self,
        app_name: str = "user_agent",
        verifier: Any = None,
        agent: Any = None,
        session_service: Any = None,
    ):
        self._app_name = app_name
        self._verifier = verifier
        self._agent = agent
        self._session_service = session_service
        self._runner = None

    def set_up(self) -> None:
        """Runs once per Agent Runtime instance."""
        from google.adk.runners import Runner

        # Agent Runtime sets GOOGLE_CLOUD_LOCATION to the engine's region, where sessions live;
        # Gemini is served from SDLC_MODEL_LOCATION (e.g. `global`, as on dev). Read the session
        # region first, then point model calls (google-genai reads the variable) at the model one.
        engine_location = os.environ.get("GOOGLE_CLOUD_LOCATION")
        model_location = os.environ.get("SDLC_MODEL_LOCATION")
        if model_location:
            os.environ["GOOGLE_CLOUD_LOCATION"] = model_location
        if self._verifier is None:
            from sdlc_agent.runtime_guard import verifier_from_env

            self._verifier = verifier_from_env()  # the stack's verifier (CH-0022)
        if self._agent is None:
            from .agent import root_agent  # agents/user_agent/agent.py (same package)

            self._agent = root_agent
        if self._session_service is None:
            self._session_service = _session_service_from_env(engine_location)
            # Agent Runtime sessions are keyed by the engine, not by a free app name
            self._app_name = os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID", self._app_name)
        self._runner = Runner(
            app_name=self._app_name, agent=self._agent, session_service=self._session_service
        )

    def register_operations(self) -> dict[str, list[str]]:
        return {"async": ["list_threads", "delete_thread"], "async_stream": ["stream_query"]}

    # Every method returns refusals as `{"error": {...}}` instead of raising (CH-0019): when a
    # method raises, Agent Runtime echoes the call's arguments, the user's token included, into
    # the error and its log.

    async def stream_query(
        self,
        message: str,
        user_token: str,
        session_id: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        try:
            async for item in self._stream(message, user_token, session_id, state):
                yield item
        except Exception as e:  # noqa: BLE001 (reported as an error result, see above)
            yield _error(e)

    async def list_threads(self, user_token: str) -> list[dict[str, Any]] | dict[str, Any]:
        try:
            return await self._list_threads(user_token)
        except Exception as e:  # noqa: BLE001
            return _error(e)

    async def delete_thread(self, user_token: str, session_id: str) -> dict[str, Any]:
        try:
            return await self._delete_thread(user_token, session_id)
        except Exception as e:  # noqa: BLE001
            return _error(e)

    async def _stream(self, message, user_token, session_id, state):
        from google.genai import types

        oid = await verify_user(self._verifier, user_token)
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message is empty")
        if len(message) > MAX_MESSAGE_CHARS:
            raise ValueError("message too long")
        session = await self._own_session(oid, session_id, state, message)
        yield {"session": session.id}
        bound = set_request_token(user_token)  # this call only; never stored in the session
        try:
            async for event in self._runner.run_async(
                user_id=oid,
                session_id=session.id,
                new_message=types.Content(role="user", parts=[types.Part(text=message)]),
            ):
                yield event.model_dump(mode="json", by_alias=True, exclude_none=True)
        finally:
            reset_request_token(bound)

    async def _list_threads(self, user_token: str) -> list[dict[str, Any]]:
        oid = await verify_user(self._verifier, user_token)
        listed = await self._session_service.list_sessions(app_name=self._app_name, user_id=oid)
        threads = [
            {
                "threadId": s.id,
                "title": (s.state or {}).get(TITLE_STATE_KEY, ""),
                "updatedAt": _iso(s.last_update_time),
            }
            for s in listed.sessions
        ]
        threads.sort(key=lambda t: t["updatedAt"], reverse=True)
        return threads[:MAX_THREADS]

    async def _delete_thread(self, user_token: str, session_id: str) -> dict[str, bool]:
        oid = await verify_user(self._verifier, user_token)
        await self._owned(oid, session_id)  # someone else's session answers "not found"
        await self._session_service.delete_session(
            app_name=self._app_name, user_id=oid, session_id=session_id
        )
        return {"deleted": True}

    async def _own_session(self, oid, session_id, state, message):
        if session_id:
            return await self._owned(oid, session_id)
        initial = clean_state(state)
        initial[TITLE_STATE_KEY] = " ".join(message.split())[:TITLE_CHARS]
        return await self._session_service.create_session(
            app_name=self._app_name, user_id=oid, state=initial
        )

    async def _owned(self, oid: str, session_id: str):
        if not isinstance(session_id, str) or not session_id:
            raise LookupError("conversation not found")
        session = await self._session_service.get_session(
            app_name=self._app_name, user_id=oid, session_id=session_id
        )
        if session is None or session.user_id != oid:
            raise LookupError("conversation not found")
        return session


def _session_service_from_env(location: str | None):
    from google.adk.sessions import VertexAiSessionService

    return VertexAiSessionService(
        project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        location=location,
        agent_engine_id=os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID"),
    )


# Expected refusals, most specific first. Messages are fixed: never an argument value or an
# exception's text, which could quote one.
_REFUSALS = (
    (
        NotAuthenticated,
        "unauthenticated",
        "sign-in required: the token is missing, invalid or expired",
    ),
    (LookupError, "not_found", "conversation not found"),
    (ValueError, "invalid_argument", "invalid request: the message is empty or too long"),
)


def _error(exc: Exception) -> dict[str, Any]:
    for kind, code, message in _REFUSALS:
        if isinstance(exc, kind):
            return {"error": {"code": code, "message": message}}
    log.warning("runtime call failed: %s", type(exc).__name__)  # the type only, never the text
    return {"error": {"code": "internal", "message": "the agent could not complete the request"}}


def _iso(ts: float | None) -> str:
    return datetime.fromtimestamp(ts or 0, UTC).isoformat()


__all__ = ["NotAuthenticated", "UserAgentApp"]

app = (
    UserAgentApp()
)  # Agent Runtime entry point: user_agent.runtime_app:app (deploy_agent_runtime.py)
