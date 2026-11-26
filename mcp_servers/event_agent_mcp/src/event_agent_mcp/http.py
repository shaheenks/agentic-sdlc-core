"""HTTP: /mcp for the event agents' runtime only, after the system identity and its run are checked."""

import json
from typing import Any

import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.transport_security import TransportSecuritySettings
from sdlc_config_store import ConfigUnavailable
from sdlc_identity import Rejected
from sdlc_logging import audit
from sdlc_service import health_routes
from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from event_agent_mcp.errors import ToolError
from event_agent_mcp.platform import Platform, Run, RunRefused

PROTECTED = "/mcp"


class AuthMiddleware:
    """Every request to /mcp must come from the system identity (a declared caller of a system surface, proved by its
    Google ID token) and name a run it may act in: one of its teams and a declared, enabled subscription. Anything
    else is refused before a handler sees it, and the refusal is audited with its reason (FR-IDN-004, FR-AGT-004)."""

    def __init__(self, app: ASGIApp, platform: Platform) -> None:
        self.app = app
        self.platform = platform

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not (path == PROTECTED or path.startswith(PROTECTED + "/")):
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        try:
            caller, bundle = await self.platform.identify(headers)
            run = self.platform.run(caller, bundle, headers)
        except Rejected as exc:
            audit("auth.denied", reason=exc.reason, path=path)
            await JSONResponse({"error": "invalid_token"}, 401)(scope, receive, send)
            return
        except RunRefused as exc:
            audit("auth.denied", reason=exc.reason, path=path)
            await JSONResponse({"error": "forbidden", "error_description": exc.reason}, 403)(scope, receive, send)
            return
        except ConfigUnavailable:
            audit("auth.denied", reason="config_unavailable", path=path)
            await JSONResponse({"error": "unavailable"}, 503)(scope, receive, send)
            return
        scope["sdlc.run"] = run
        await self.app(scope, receive, send)


def _text(result: dict[str, Any]) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(result))]


def mcp_server(platform: Platform) -> Server:
    def run_of(ctx) -> Run:
        return ctx.request.scope["sdlc.run"]

    async def on_list_tools(ctx, params) -> types.ListToolsResult:
        tools = platform.visible_tools(run_of(ctx))
        return types.ListToolsResult(
            tools=[types.Tool(name=t.name, description=t.description, input_schema=t.input_schema) for t in tools]
        )

    async def on_call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        try:
            result = await platform.invoke(run_of(ctx), params.name, dict(params.arguments or {}))
        except ToolError as exc:
            return types.CallToolResult(content=_text({"error": exc.code, "message": exc.message}), is_error=True)
        return types.CallToolResult(content=_text(result), structured_content=result)

    return Server(
        "event_agent_mcp",
        version="0.1.0",
        instructions="Tools of unattended runs, acting as the system identity on the run's team's systems.",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


def build_app(platform: Platform, service: str) -> Starlette:
    app = mcp_server(platform).streamable_http_app(
        streamable_http_path=PROTECTED,
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        custom_starlette_routes=health_routes(service),
    )
    app.add_middleware(AuthMiddleware, platform=platform)
    return app
