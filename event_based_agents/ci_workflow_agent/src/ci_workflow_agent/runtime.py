"""The Agent Runtime application of the event agents (DEC-0007, DEC-0015).

Only the event gateway calls it, with its own service account: it creates one session per run with the run in the
session's state, then streams the event into it. Every session belongs to the one user `system`; the state may hold
only the run's keys, so nothing else can steer what the run does or which headers it sends."""

from typing import TYPE_CHECKING, Any

from vertexai.agent_engines import AdkApp

from ci_workflow_agent.identity import RUN, STATE_KEYS, SUBSCRIPTION, SYSTEM_USER, TEAM, WORKFLOW

if TYPE_CHECKING:
    from google.adk.apps import App

REQUIRED = (TEAM, SUBSCRIPTION, RUN, WORKFLOW)


class Refused(ValueError):
    """A request the application does not serve; the message says why, never echoing argument values."""


class CiWorkflowApp(AdkApp):
    def register_operations(self) -> dict[str, list[str]]:
        return {"async": ["async_create_session", "async_get_session"], "async_stream": ["async_stream_query"]}

    async def async_create_session(self, *, user_id: str, state: dict[str, Any] | None = None, **kwargs):
        state = dict(state or {})
        if user_id != SYSTEM_USER:
            raise Refused(f"runs belong to the user {SYSTEM_USER}")
        if set(state) - set(STATE_KEYS):
            raise Refused(f"state may hold only {', '.join(STATE_KEYS)}")
        if not all(isinstance(state.get(k), str) and state[k] for k in REQUIRED):
            raise Refused(f"a run needs {', '.join(REQUIRED)}")
        return await super().async_create_session(user_id=user_id, state=state)

    async def async_get_session(self, *, user_id: str, session_id: str, **kwargs):
        return await super().async_get_session(user_id=user_id, session_id=session_id)

    async def async_stream_query(self, *, message, user_id: str, session_id: str | None = None, **kwargs):
        if user_id != SYSTEM_USER or not session_id:
            raise Refused("a query needs the session_id of a run")
        if kwargs.get("session_events"):
            raise Refused("session events cannot be supplied")
        await super().async_get_session(user_id=user_id, session_id=session_id)
        async for event in super().async_stream_query(message=message, user_id=user_id, session_id=session_id):
            yield event


def adk_app(root) -> "App":
    """Resumable, so a retried task continues the run from where it stopped."""
    from google.adk.apps import App, ResumabilityConfig

    return App(name="ci_workflow_agent", root_agent=root, resumability_config=ResumabilityConfig(is_resumable=True))


def create_app() -> CiWorkflowApp:
    from ci_workflow_agent.agent import build_agent

    return CiWorkflowApp(app=adk_app(build_agent()))
