"""The user agent on Agent Runtime (GCP-native hosting, design D17, CH-0014).

`adk web` + `sdlc_web` serve the agent locally and on GCP dev. On Agent Runtime there is no web
layer of ours, so this app is the entry point and runs the same checks first
(`sdlc_agent.runtime_guard`):
- every call carries the user's Entra token, which is re-validated (fail closed);
- the ADK user id is the token's `oid`; a caller can never pick another user's id or session;
- client state is cleaned (no tokens, `temp:`, `app:`, `user:` or `sdlc_` keys);
- the token is bound for this call only (`sdlc_auth.adk.set_request_token`), so the agent's MCP
  calls carry it, and it is never written to the session.

Operations (`register_operations`):
- `stream_query(message, user_token, session_id=None, state=None)`: async stream of ADK events
  (JSON), the first being `{"session": <id>}` so a client can continue the conversation;
- `list_threads(user_token)`: the caller's conversations, newest first (id, title, updatedAt);
- `delete_thread(user_token, session_id)`: deletes one of the caller's conversations.

The Agent Runtime caller (the UI service account) is trusted to reach the engine, never to speak
for a user: who the user is comes only from the token.
"""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sdlc_agent.runtime_guard import NotAuthenticated, clean_state, verify_user
from sdlc_auth.adk import reset_request_token, set_request_token

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

        if self._verifier is None:
            from sdlc_auth.entra import verifier_from_env

            self._verifier = verifier_from_env()
        if self._agent is None:
            from .agent import root_agent  # agents/user_agent/agent.py (same package)

            self._agent = root_agent
        if self._session_service is None:
            self._session_service = _session_service_from_env()
            # Agent Runtime sessions are keyed by the engine, not by a free app name
            self._app_name = os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID", self._app_name)
        self._runner = Runner(
            app_name=self._app_name, agent=self._agent, session_service=self._session_service
        )

    def register_operations(self) -> dict[str, list[str]]:
        return {"async": ["list_threads", "delete_thread"], "async_stream": ["stream_query"]}

    async def stream_query(
        self,
        message: str,
        user_token: str,
        session_id: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        from google.genai import types

        oid = await verify_user(self._verifier, user_token)
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message is empty")
        if len(message) > MAX_MESSAGE_CHARS:
            raise ValueError(f"message is longer than {MAX_MESSAGE_CHARS} characters")
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

    async def list_threads(self, user_token: str) -> list[dict[str, Any]]:
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

    async def delete_thread(self, user_token: str, session_id: str) -> dict[str, bool]:
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


def _session_service_from_env():
    from google.adk.sessions import VertexAiSessionService

    return VertexAiSessionService(
        project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        location=os.environ.get("GOOGLE_CLOUD_LOCATION"),
        agent_engine_id=os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID"),
    )


def _iso(ts: float | None) -> str:
    return datetime.fromtimestamp(ts or 0, UTC).isoformat()


__all__ = ["NotAuthenticated", "UserAgentApp"]

app = (
    UserAgentApp()
)  # Agent Runtime entry point: user_agent.runtime_app:app (deploy_agent_runtime.py)
