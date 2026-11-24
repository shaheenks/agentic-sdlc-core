"""HTTP service basics: health route and server entry point."""

import os

import uvicorn
from sdlc_logging import configure_logging
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


def health_routes(service: str) -> list[Route]:
    """`GET /healthz` answers 200 with the service name."""

    async def healthz(request: Request) -> JSONResponse:
        return JSONResponse({"service": service, "status": "ok"})

    return [Route("/healthz", healthz, methods=["GET"])]


def serve(app, service: str, default_port: int) -> None:
    """Run the app with uvicorn on HOST/PORT, logging as JSON."""
    configure_logging(service)
    uvicorn.run(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", default_port)),
        log_config=None,
    )
