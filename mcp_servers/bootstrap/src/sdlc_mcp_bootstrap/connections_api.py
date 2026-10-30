"""Connections API (version-01 §4.4): users connect and disconnect their own accounts.

  GET    /connections/            the caller's connections (status only, never tokens)
  PUT    /connections/{id}        {"token", "username"?, "expires_at"?: "YYYY-MM-DD"}
  DELETE /connections/{id}

Served by the MCP server (the only service that holds user secrets), reached by the browser through
oauth2-proxy at /connections/: the proxy adds the user's Entra token (X-Forwarded-Access-Token);
`Authorization: Bearer` works too. The token is validated by the same verifier as MCP requests
(issuer, audience, scope, tenant, block list). Never through chat: a PAT typed into a chat would
reach the model and the conversation history.

State-changing calls need `X-SDLC-Connections: 1` and a JSON body (a cross-site form or image
request cannot send either), so another site cannot connect or disconnect for a signed-in user.
Audit: `connection_change` (oid, connection, action, outcome, reason); never the token.
"""

import json
import logging
from datetime import UTC, date, datetime

from fastmcp import FastMCP
from fastmcp.server.auth import TokenVerifier
from sdlc_auth import principal_from_claims
from sdlc_connectors.service import ConnectError
from sdlc_connectors.user_store import UserStoreError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from sdlc_mcp_bootstrap.audit import emit, new_request_id
from sdlc_mcp_bootstrap.connected_tools import Connected

log = logging.getLogger("sdlc.mcp")
MAX_BODY = 8 * 1024
CSRF_HEADER = "x-sdlc-connections"


def _token(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-access-token", "").strip()
    if forwarded:
        return forwarded
    auth = request.headers.get("authorization", "")
    return auth[7:].strip() if auth[:7].lower() == "bearer " else None


def add_connection_routes(mcp: FastMCP, connected: Connected, verifier: TokenVerifier) -> None:
    async def caller(request: Request) -> str | Response:
        token = _token(request)
        access = await verifier.load_access_token(token) if token else None
        if access is None:
            return JSONResponse({"detail": "sign-in required"}, status_code=401)
        try:
            return principal_from_claims(access.claims).oid
        except ValueError:
            return JSONResponse({"detail": "not a user token"}, status_code=401)

    def unavailable() -> JSONResponse:
        return JSONResponse(
            {"detail": "user connections are not configured on this server"}, status_code=503
        )

    def audit(oid: str, action: str, connection: str, outcome: str, reason: str = "") -> None:
        emit(
            {
                "event": "connection_change",
                "ts": datetime.now(UTC).isoformat(),
                "request_id": new_request_id(),
                "oid": oid,
                "action": action,
                "connection": connection,
                "outcome": outcome,
                **({"reason": reason[:300]} if reason else {}),
            }
        )

    @mcp.custom_route("/connections/", methods=["GET"])
    async def list_connections(request: Request) -> Response:
        oid = await caller(request)
        if isinstance(oid, Response):
            return oid
        if connected.service is None:
            return unavailable()
        try:
            items = await connected.service.status(oid)
        except UserStoreError as e:
            log.error("user connections unreadable: %s", e)
            return JSONResponse({"detail": "your connections cannot be read"}, status_code=500)
        return JSONResponse({"connections": items})

    @mcp.custom_route("/connections/{connection_id}", methods=["PUT", "DELETE"])
    async def change_connection(request: Request) -> Response:
        oid = await caller(request)
        if isinstance(oid, Response):
            return oid
        if request.headers.get(CSRF_HEADER) != "1":
            return JSONResponse({"detail": f"missing {CSRF_HEADER} header"}, status_code=403)
        if connected.service is None:
            return unavailable()
        connection_id = request.path_params["connection_id"]
        if request.method == "DELETE":
            removed = await connected.service.disconnect(oid, connection_id)
            audit(oid, "disconnect", connection_id, "ok" if removed else "not_connected")
            return JSONResponse({"id": connection_id, "connected": False})

        if not request.headers.get("content-type", "").startswith("application/json"):
            return JSONResponse({"detail": "send JSON"}, status_code=415)
        body = await request.body()
        if len(body) > MAX_BODY:
            return JSONResponse({"detail": "request too large"}, status_code=413)
        try:
            payload = json.loads(body)
            token = str(payload["token"])
            username = payload.get("username")
            expires = payload.get("expires_at")
            expires_at = date.fromisoformat(expires) if expires else None
        except (ValueError, KeyError, TypeError):
            return JSONResponse(
                {"detail": "expected {token, username?, expires_at?}"}, status_code=400
            )
        try:
            result = await connected.service.connect(
                oid, connection_id, token, username, expires_at
            )
        except ConnectError as e:
            audit(oid, "connect", connection_id, "rejected", str(e))
            return JSONResponse({"detail": str(e)}, status_code=422)
        except UserStoreError as e:
            audit(oid, "connect", connection_id, "error", type(e).__name__)
            log.error("user connection not saved: %s", e)
            return JSONResponse({"detail": "the connection could not be saved"}, status_code=500)
        audit(oid, "connect", connection_id, "ok")
        return JSONResponse(result)
