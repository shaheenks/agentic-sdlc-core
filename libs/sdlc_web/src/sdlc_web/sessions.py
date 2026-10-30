"""Conversation store on GCP: Vertex AI Agent Engine sessions (version-01 M8).

`SDLC_SESSION_SERVICE_URI=agentengine://projects/<p>/locations/<region>/reasoningEngines/<id>`
selects it. `register_agent_engine_sessions` replaces ADK's built-in `agentengine` factory in
ADK's service registry, so adk web and /agui (both build their store from the URI) get the same
behaviour:
- only the full resource name is accepted: the engine is regional, while the model's
  GOOGLE_CLOUD_LOCATION is `global`, so a short id would pick the wrong location (fail at startup);
- every new session gets a TTL of SDLC_SESSION_RETENTION_DAYS, so Agent Engine deletes it with its
  events. Retention counts from the start of the conversation (SQLite locally: idle time).
"""

import re
from typing import Any
from urllib.parse import urlparse

from google.adk.cli.service_registry import get_service_registry
from google.adk.sessions.base_session_service import BaseSessionService
from google.adk.sessions.session import Session
from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService

SCHEME = "agentengine"
_RESOURCE = re.compile(
    r"^projects/(?P<project>[a-z0-9-]+)/locations/(?P<location>[a-z0-9-]+)"
    r"/reasoningEngines/(?P<engine>\d+)$"
)


class RetainedVertexAiSessionService(VertexAiSessionService):
    """Agent Engine sessions that expire `ttl_seconds` after they are created."""

    def __init__(self, *, project: str, location: str, agent_engine_id: str, ttl_seconds: int):
        if ttl_seconds <= 0:
            raise ValueError("session retention must be positive")
        super().__init__(project=project, location=location, agent_engine_id=agent_engine_id)
        self.ttl_seconds = ttl_seconds

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: dict[str, Any] | None = None,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> Session:
        if kwargs.get("expire_time") is None:  # an explicit expiry from the caller wins
            kwargs.setdefault("ttl", f"{self.ttl_seconds}s")
        return await super().create_session(
            app_name=app_name, user_id=user_id, state=state, session_id=session_id, **kwargs
        )


def parse_agent_engine_uri(uri: str) -> tuple[str, str, str]:
    """(project, location, engine id) from `agentengine://projects/…/reasoningEngines/<id>`."""
    parsed = urlparse(uri)
    if parsed.scheme != SCHEME:
        raise ValueError(f"not an {SCHEME}:// URI")
    match = _RESOURCE.fullmatch(parsed.netloc + parsed.path)
    if not match:
        raise ValueError(
            "SDLC_SESSION_SERVICE_URI must name the full Agent Engine resource: "
            "agentengine://projects/<project>/locations/<region>/reasoningEngines/<id>"
        )
    return match["project"], match["location"], match["engine"]


def register_agent_engine_sessions(retention_days: float) -> None:
    """Make `agentengine://` URIs build a RetainedVertexAiSessionService (process-wide)."""
    ttl_seconds = int(retention_days * 86400)

    def factory(uri: str, **_kwargs: Any) -> BaseSessionService:
        project, location, engine = parse_agent_engine_uri(uri)
        return RetainedVertexAiSessionService(
            project=project, location=location, agent_engine_id=engine, ttl_seconds=ttl_seconds
        )

    get_service_registry().register_session_service(SCHEME, factory)
