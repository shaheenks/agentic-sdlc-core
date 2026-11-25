"""The Agent Runtime application (DEC-0004, DEC-0010).

Only sdlc_ui calls it, with its service account, for the user it verified: it creates a session per chat with
the user's ID and email, then streams queries into that session. Sessions are keyed by the user ID, so a user
who signs in again finds and continues them (FR-WFL-009); every operation names the user, and a session of
another user is never found (FR-AUTHZ-008).

Compared with `AdkApp`, a query must name an existing session (whose state holds the email), cannot inject
session events, and memory operations are not offered."""

from typing import Any

from vertexai.agent_engines import AdkApp

from user_agent.identity import EMAIL_KEY, TEAM_KEY, TITLE_KEY

ALLOWED_STATE = {EMAIL_KEY, TEAM_KEY, TITLE_KEY}


class Refused(ValueError):
    """A request the application does not serve; the message says why, never echoing argument values."""


class UserAgentApp(AdkApp):
    def register_operations(self) -> dict[str, list[str]]:
        return {
            "async": ["async_create_session", "async_get_session", "async_list_sessions", "async_delete_session"],
            "async_stream": ["async_stream_query"],
        }

    async def async_create_session(self, *, user_id: str, state: dict[str, Any] | None = None, **kwargs):
        state = dict(state or {})
        if set(state) - ALLOWED_STATE:
            raise Refused(f"state may hold only {', '.join(sorted(ALLOWED_STATE))}")
        if not isinstance(state.get(EMAIL_KEY), str) or not state[EMAIL_KEY]:
            raise Refused(f"a session needs {EMAIL_KEY}")
        return await super().async_create_session(user_id=user_id, state=state)

    async def async_stream_query(self, *, message, user_id: str, session_id: str | None = None, **kwargs):
        if not session_id:
            raise Refused("a query needs the session_id of a session created for this user")
        if kwargs.get("session_events"):
            raise Refused("session events cannot be supplied")
        # Raises when the session is not this user's, before anything runs.
        await super().async_get_session(user_id=user_id, session_id=session_id)
        async for event in super().async_stream_query(message=message, user_id=user_id, session_id=session_id):
            yield event


def create_app() -> UserAgentApp:
    from user_agent.agent import build_agent

    return UserAgentApp(agent=build_agent())
