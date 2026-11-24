"""The MCP server for calls made as a user (DEC-0002).

Phase 0 skeleton: the health endpoint only.
"""

from sdlc_service import health_routes
from starlette.applications import Starlette

SERVICE = "user_agent_mcp"
DEFAULT_PORT = 8080


def create_app() -> Starlette:
    return Starlette(routes=health_routes(SERVICE))
