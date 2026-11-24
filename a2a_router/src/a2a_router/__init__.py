"""The A2A entry point to user_agent for Gemini Enterprise and later third-party surfaces.

Phase 0 skeleton: the health endpoint only.
"""

from sdlc_service import health_routes
from starlette.applications import Starlette

SERVICE = "a2a_router"
DEFAULT_PORT = 8082


def create_app() -> Starlette:
    return Starlette(routes=health_routes(SERVICE))
