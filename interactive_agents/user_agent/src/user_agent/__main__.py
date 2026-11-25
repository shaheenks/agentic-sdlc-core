"""The runtime application served locally over HTTP, in Agent Runtime's own request shape, so sdlc_ui calls
it the same way in Docker Compose as in Google Cloud:

    POST /v1/<anything>:query                 {"class_method": "async_list_sessions", "input": {...}}
    POST /v1/<anything>:streamQuery?alt=sse   {"class_method": "async_stream_query", "input": {...}}

Sessions are kept in memory. Local only: there is no caller check (SDLC_ENV must be local)."""

import json
import os

from sdlc_logging import configure_logging
from sdlc_service import health_routes, serve
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from user_agent import NAME
from user_agent.runtime import UserAgentApp, create_app

DEFAULT_PORT = 8085


def _json(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True, exclude_none=True)
    if isinstance(value, dict):
        return {k: _json(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json(v) for v in value]
    return value


def create_server(app: UserAgentApp) -> Starlette:
    operations = app.register_operations()

    async def body_of(request: Request, kind: str):
        body = await request.json()
        method = body.get("class_method")
        if method not in operations.get(kind, []):
            return None, JSONResponse({"error": {"code": 400, "message": "unknown class_method"}}, 400)
        return (method, body.get("input") or {}), None

    async def query(request: Request):
        parsed, error = await body_of(request, "async")
        if error:
            return error
        method, args = parsed
        try:
            return JSONResponse({"output": _json(await getattr(app, method)(**args))})
        except (ValueError, RuntimeError) as exc:
            return JSONResponse({"error": {"code": 400, "message": str(exc)}}, 400)

    async def stream(request: Request):
        parsed, error = await body_of(request, "async_stream")
        if error:
            return error
        method, args = parsed

        async def events():
            try:
                async for event in getattr(app, method)(**args):
                    yield f"data: {json.dumps(_json(event))}\n\n"
            except (ValueError, RuntimeError) as exc:
                yield f"data: {json.dumps({'error': {'code': 400, 'message': str(exc)}})}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    async def route(request: Request):
        action = request.path_params["path"].rpartition(":")[2]
        if action == "query":
            return await query(request)
        if action == "streamQuery":
            return await stream(request)
        return JSONResponse({"error": {"code": 404, "message": "not found"}}, 404)

    return Starlette(routes=[*health_routes(NAME), Route("/v1/{path:path}", route, methods=["POST"])])


def main() -> None:
    configure_logging(NAME)
    if os.environ.get("SDLC_ENV", "local") != "local":
        raise SystemExit("the local runtime server runs only in the local environment")
    serve(create_server(create_app()), NAME, DEFAULT_PORT)


if __name__ == "__main__":
    main()
