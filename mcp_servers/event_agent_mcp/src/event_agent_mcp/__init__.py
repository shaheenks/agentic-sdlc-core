"""The MCP server for scheduled and event-triggered runs, as the system identity (DEC-0007).

Phase 0 skeleton: the health endpoint only.
"""

from sdlc_service import health_routes
from starlette.applications import Starlette

SERVICE = "event_agent_mcp"
DEFAULT_PORT = 8081


def create_app() -> Starlette:
    return Starlette(routes=health_routes(SERVICE))
