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
- `stream_query(message, user_token, session_id=None, state=None, thread_id=None)`: async stream
  of ADK events (JSON), the first being `{"session": <id>}` so a client can continue the
  conversation. `thread_id` (CH-0016) is a client's name for the conversation (the chat UI's AG-UI
  thread id): the caller's session with that name, or a new one carrying it;
- `list_threads(user_token)`: the caller's conversations, newest first (threadId = the client's
  name if it gave one, else the session id; title, updatedAt);
- `get_thread(user_token, session_id=None, thread_id=None)` (CH-0016): one of the caller's
  conversations as AG-UI messages (user, assistant with tool calls, tool results);
- `delete_thread(user_token, session_id)`: deletes one of the caller's conversations (a session id
  or a thread name).

A refusal is a result, never an exception: `{"refusal": {"code", "message"}}` (for `stream_query`, a
single event), with code `unauthenticated`, `not_found`, `invalid_argument` or `internal` (CH-0019).
Not `error` (CH-0025): google.genai takes a streamed `{"error": ...}` chunk for an API error.

The Agent Runtime caller (the UI service account) is trusted to reach the engine, never to speak
for a user: who the user is comes only from the token.
"""

import json
import logging
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sdlc_agent.runtime_guard import NotAuthenticated, clean_state, verify_user
from sdlc_auth.adk import reset_request_token, set_request_token

log = logging.getLogger(__name__)

TITLE_STATE_KEY = "sdlc_title"  # server-owned: set from the first message, never by a client
THREAD_STATE_KEY = "sdlc_thread_id"  # server-owned: the client's name for the session (CH-0016)
THREAD_ID_CHARS = 128
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
        return {
            "async": ["list_threads", "get_thread", "delete_thread"],
            "async_stream": ["stream_query"],
        }

    # Every method returns refusals as `{"refusal": {...}}` instead of raising (CH-0019): when a
    # method raises, Agent Runtime echoes the call's arguments, the user's token included, into
    # the error and its log.

    async def stream_query(
        self,
        message: str,
        user_token: str,
        session_id: str | None = None,
        state: dict[str, Any] | None = None,
        thread_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        try:
            async for item in self._stream(message, user_token, session_id, state, thread_id):
                yield item
        except Exception as e:  # noqa: BLE001 (reported as an error result, see above)
            yield _error(e)

    async def list_threads(self, user_token: str) -> list[dict[str, Any]] | dict[str, Any]:
        try:
            return await self._list_threads(user_token)
        except Exception as e:  # noqa: BLE001
            return _error(e)

    async def get_thread(
        self, user_token: str, session_id: str | None = None, thread_id: str | None = None
    ) -> dict[str, Any]:
        try:
            return await self._get_thread(user_token, session_id, thread_id)
        except Exception as e:  # noqa: BLE001
            return _error(e)

    async def delete_thread(self, user_token: str, session_id: str) -> dict[str, Any]:
        try:
            return await self._delete_thread(user_token, session_id)
        except Exception as e:  # noqa: BLE001
            return _error(e)

    async def _stream(self, message, user_token, session_id, state, thread_id=None):
        from google.genai import types

        oid = await verify_user(self._verifier, user_token)
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message is empty")
        if len(message) > MAX_MESSAGE_CHARS:
            raise ValueError("message too long")
        _check_thread_id(thread_id)
        session = await self._own_session(oid, session_id, state, message, thread_id)
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
                "threadId": (s.state or {}).get(THREAD_STATE_KEY) or s.id,
                "title": (s.state or {}).get(TITLE_STATE_KEY, ""),
                "updatedAt": _iso(s.last_update_time),
            }
            for s in listed.sessions
        ]
        threads.sort(key=lambda t: t["updatedAt"], reverse=True)
        return threads[:MAX_THREADS]

    async def _get_thread(self, user_token, session_id, thread_id) -> dict[str, Any]:
        oid = await verify_user(self._verifier, user_token)
        _check_thread_id(thread_id)
        if session_id:
            session = await self._owned(oid, session_id)
        else:
            session = await self._named(oid, thread_id)
            if session is None:
                raise LookupError("conversation not found")
        name = (session.state or {}).get(THREAD_STATE_KEY) or session.id
        return {"threadId": name, "messages": thread_messages(session.events)}

    async def _delete_thread(self, user_token: str, session_id: str) -> dict[str, bool]:
        oid = await verify_user(self._verifier, user_token)
        # a session id or a thread name; someone else's answers "not found"
        session = await self._named(oid, session_id) if _is_name(session_id) else None
        session = session or await self._owned(oid, session_id)
        await self._session_service.delete_session(
            app_name=self._app_name, user_id=oid, session_id=session.id
        )
        return {"deleted": True}

    async def _own_session(self, oid, session_id, state, message, thread_id=None):
        if session_id:
            return await self._owned(oid, session_id)
        if thread_id:
            named = await self._named(oid, thread_id)
            if named is not None:
                return named
        initial = clean_state(state)  # drops sdlc_ keys: a client cannot claim a thread name
        initial[TITLE_STATE_KEY] = " ".join(message.split())[:TITLE_CHARS]
        if thread_id:
            initial[THREAD_STATE_KEY] = thread_id
        return await self._session_service.create_session(
            app_name=self._app_name, user_id=oid, state=initial
        )

    async def _named(self, oid: str, thread_id: str | None):
        """The caller's session that carries this thread name, with its events, or None. A
        conversation from before thread names (CH-0016) is listed under its session id, so a
        name that matches no session is also tried as one of the caller's own session ids."""
        if not thread_id:
            return None
        listed = await self._session_service.list_sessions(app_name=self._app_name, user_id=oid)
        for s in listed.sessions:
            if (s.state or {}).get(THREAD_STATE_KEY) == thread_id:
                return await self._owned(oid, s.id)
        if not any(s.id == thread_id for s in listed.sessions):
            return None  # not one of the caller's sessions either
        return await self._owned(oid, thread_id)

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
    (ValueError, "invalid_argument", "invalid request: the message or thread id is not valid"),
)


def _error(exc: Exception) -> dict[str, Any]:
    for kind, code, message in _REFUSALS:
        if isinstance(exc, kind):
            return {"refusal": {"code": code, "message": message}}
    log.warning("runtime call failed: %s", type(exc).__name__)  # the type only, never the text
    return {"refusal": {"code": "internal", "message": "the agent could not complete the request"}}


def _check_thread_id(thread_id: Any) -> None:
    if thread_id is not None and not _is_name(thread_id):
        raise ValueError("invalid thread id")


def _is_name(value: Any) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= THREAD_ID_CHARS
        and all(c.isalnum() or c in "-_" for c in value)
    )


def thread_messages(events: list[Any]) -> list[dict[str, Any]]:
    """ADK session events as AG-UI messages, the shape adk web's /agents/state gives the chat UI:
    user text, assistant text and tool calls, tool results (JSON text, as in the live stream).
    Partial events and thoughts are left out."""
    messages: list[dict[str, Any]] = []
    for event in events or []:
        content = getattr(event, "content", None)
        if content is None or not content.parts or getattr(event, "partial", False):
            continue
        event_id = getattr(event, "id", None) or ""
        text = "".join(p.text for p in content.parts if p.text and not p.thought)
        calls = [p.function_call for p in content.parts if p.function_call]
        results = [p.function_response for p in content.parts if p.function_response]
        if results:
            for i, r in enumerate(results):
                messages.append(
                    {
                        "id": f"{event_id}-r{i}",
                        "role": "tool",
                        "toolCallId": r.id or f"{event_id}-c{i}",
                        "content": json.dumps(r.response, ensure_ascii=False, default=str),
                    }
                )
            continue
        if getattr(event, "author", None) == "user":
            if text:
                messages.append({"id": event_id, "role": "user", "content": text})
            continue
        if not text and not calls:
            continue
        message: dict[str, Any] = {"id": event_id, "role": "assistant"}
        if text:
            message["content"] = text
        if calls:
            message["toolCalls"] = [
                {
                    "id": c.id or f"{event_id}-c{i}",
                    "type": "function",
                    "function": {"name": c.name, "arguments": json.dumps(c.args or {})},
                }
                for i, c in enumerate(calls)
            ]
        messages.append(message)
    return messages


def _iso(ts: float | None) -> str:
    return datetime.fromtimestamp(ts or 0, UTC).isoformat()


__all__ = ["NotAuthenticated", "UserAgentApp"]

app = (
    UserAgentApp()
)  # Agent Runtime entry point: user_agent.runtime_app:app (deploy_agent_runtime.py)
