"""Knowledge search over the JSONL knowledge store, filtered by the caller's data scope.

Phase 0 skeleton: the health endpoint only.
"""

from sdlc_service import health_routes
from starlette.applications import Starlette

SERVICE = "knowledge_search"
DEFAULT_PORT = 8083


def create_app() -> Starlette:
    return Starlette(routes=health_routes(SERVICE))
