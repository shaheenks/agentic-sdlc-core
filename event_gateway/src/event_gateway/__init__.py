"""Receives, verifies, deduplicates and triages events, and starts unattended runs.

Phase 0 skeleton: the health endpoint only.
"""

from sdlc_service import health_routes
from starlette.applications import Starlette

SERVICE = "event_gateway"
DEFAULT_PORT = 8084


def create_app() -> Starlette:
    return Starlette(routes=health_routes(SERVICE))
