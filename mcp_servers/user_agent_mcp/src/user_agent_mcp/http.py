"""HTTP: authentication for /mcp and /api, the MCP handlers, the HTTP API for sdlc_ui, and the OAuth
protected-resource metadata that names Google as the authorization server."""

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
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from user_agent_mcp.errors import ToolError
from user_agent_mcp.platform import Caller, Platform

GOOGLE_ISSUER = "https://accounts.google.com"
PROTECTED = ("/mcp", "/api/")
METADATA_PATH = "/.well-known/oauth-protected-resource"


def _bearer(scope: Scope) -> str:
    for key, value in scope.get("headers") or ():
        if key.lower() == b"authorization":
            text = value.decode("latin-1")
            if text[:7].lower() == "bearer ":
                return text[7:].strip()
    return ""


class AuthMiddleware:
    """Every request to /mcp and /api needs a verified Google account token of a declared surface; anything
    else is refused before it reaches a handler, and the refusal is audited with its reason (FR-IDN-001,
    NFR-SEC-002). Health checks and the metadata document are public."""

    def __init__(self, app: ASGIApp, platform: Platform) -> None:
        self.app = app
        self.platform = platform
        self.metadata_url = f"{platform.settings.public_url}{METADATA_PATH}"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not any(path == p or path.startswith(p) for p in PROTECTED):
            await self.app(scope, receive, send)
            return
        try:
            token = _bearer(scope)
            if not token:
                raise Rejected("no_token")
            identity, bundle = await self.platform.identify(token)
        except Rejected as exc:
            audit("auth.denied", reason=exc.reason, path=path)
            await self._refuse(scope, receive, send, 401, "invalid_token", "authentication required")
            return
        except ConfigUnavailable:
            audit("auth.denied", reason="config_unavailable", path=path)
            await self._refuse(scope, receive, send, 503, "unavailable", "configuration unavailable")
            return
        scope["sdlc.identity"], scope["sdlc.bundle"] = identity, bundle
        await self.app(scope, receive, send)

    async def _refuse(self, scope: Scope, receive: Receive, send: Send, status: int, error: str, text: str) -> None:
        headers = {"WWW-Authenticate": f'Bearer error="{error}", resource_metadata="{self.metadata_url}"'}
        await JSONResponse({"error": error, "error_description": text}, status, headers)(scope, receive, send)


async def _caller(platform: Platform, request: Request) -> Caller:
    return await platform.caller(request.scope["sdlc.identity"], request.scope["sdlc.bundle"], request.headers)


def _text(result: dict[str, Any]) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(result))]


def mcp_server(platform: Platform) -> Server:
    async def on_list_tools(ctx, params) -> types.ListToolsResult:
        caller = await _caller(platform, ctx.request)
        tools = platform.visible_tools(caller, "mcp")
        return types.ListToolsResult(
            tools=[types.Tool(name=t.name, description=t.description, input_schema=t.input_schema) for t in tools]
        )

    async def on_call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        caller = await _caller(platform, ctx.request)
        try:
            result = await platform.invoke(caller, params.name, dict(params.arguments or {}), "mcp")
        except ToolError as exc:
            return types.CallToolResult(content=_text({"error": exc.code, "message": exc.message}), is_error=True)
        return types.CallToolResult(content=_text(result), structured_content=result)

    return Server(
        "user_agent_mcp",
        version="0.1.0",
        instructions="Tools that act for the signed-in user on their own artifacts and connections.",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


def api_routes(platform: Platform) -> list[Route]:
    """The same operations for sdlc_ui, each mapped to its tool so the same policy and audit apply."""

    def endpoint(tool: str, args_from):
        async def handle(request: Request) -> JSONResponse:
            caller = await _caller(platform, request)
            try:
                args = await args_from(request)
                return JSONResponse(await platform.invoke(caller, tool, args, "api"))
            except ToolError as exc:
                return JSONResponse({"error": exc.code, "message": exc.message}, exc.http_status)

        return handle

    async def nothing(request: Request) -> dict:
        return {}

    async def name(request: Request) -> dict:
        args: dict[str, Any] = {"name": request.path_params["name"]}
        if "version" in request.query_params:
            try:
                args["version"] = int(request.query_params["version"])
            except ValueError as exc:
                raise ToolError("invalid_argument", "version must be a positive integer") from exc
        return args

    async def provider(request: Request) -> dict:
        return {"provider": request.path_params["provider"]}

    async def secret(request: Request) -> dict:
        try:
            body = await request.json()
        except ValueError as exc:
            raise ToolError("invalid_argument", "expected a JSON body") from exc
        if not isinstance(body, dict):
            raise ToolError("invalid_argument", "expected a JSON object")
        allowed = {k: body[k] for k in ("secret", "account", "base_url") if k in body}
        return {**allowed, "provider": request.path_params["provider"]}

    return [
        Route("/api/me", endpoint("whoami", nothing), methods=["GET"]),
        Route("/api/artifacts", endpoint("artifact_list", nothing), methods=["GET"]),
        Route("/api/artifacts/{name}", endpoint("artifact_read", name), methods=["GET"]),
        Route("/api/artifacts/{name}", endpoint("artifact_delete", name), methods=["DELETE"]),
        Route("/api/connections", endpoint("connection_list", nothing), methods=["GET"]),
        Route("/api/connections/{provider}", endpoint("connection_save", secret), methods=["PUT"]),
        Route("/api/connections/{provider}", endpoint("connection_revoke", provider), methods=["DELETE"]),
    ]


def metadata_routes(platform: Platform) -> list[Route]:
    """OAuth protected-resource metadata (RFC 9728): Google issues the tokens this server accepts."""
    document = {
        "resource": f"{platform.settings.public_url}/mcp",
        "authorization_servers": [GOOGLE_ISSUER],
        "scopes_supported": ["openid", "email"],
        "bearer_methods_supported": ["header"],
    }

    async def metadata(request: Request) -> JSONResponse:
        return JSONResponse(document)

    return [Route(METADATA_PATH, metadata, methods=["GET"]), Route(f"{METADATA_PATH}/mcp", metadata, methods=["GET"])]


def build_app(platform: Platform, service: str) -> Starlette:
    server = mcp_server(platform)
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        # Bearer tokens, not cookies, authenticate every call, and Cloud Run sets the host name.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        custom_starlette_routes=health_routes(service) + metadata_routes(platform) + api_routes(platform),
    )
    app.add_middleware(AuthMiddleware, platform=platform)
    return app
