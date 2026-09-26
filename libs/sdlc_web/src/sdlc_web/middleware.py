"""ASGI middleware in front of ADK's FastAPI app (adk web).

For every request except public health checks:
  1. Take the user's Entra access token from X-Forwarded-Access-Token (set by oauth2-proxy)
     or `Authorization: Bearer`. Re-validate it (signature, issuer, audience, scope, tenant):
     a forged or expired header gets 401, even if the proxy is bypassed.
  2. Bind ADK's user id to the token's `oid`, in `/apps/{app}/users/{user_id}/...` paths and in
     the `user_id` of /run and /run_sse bodies. Users can only reach their own sessions,
     whatever the UI sends.
  3. Put the token in a request-scoped ContextVar for `sdlc_auth.adk.bearer_header_provider`,
     so the agent's MCP calls carry the user's identity.
  4. Restrict ADK's developer tools (`/dev/*`) to what the chat UI needs (graph views,
     user-bound routes, and the trace of the caller's OWN session). Builder save, deploy,
     evals, tests and event traces are refused (403); the UI's load-time listings get empty
     results. `dev_tools=True` (SDLC_DEV_TOOLS) re-enables everything for local development.
WebSocket (/run_live) is refused until it can be bound the same way.
Authorization stays in the MCP server; this layer only authenticates and binds identity.
"""

import json
import re
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from fastmcp.server.auth import TokenVerifier
from sdlc_auth import principal_from_claims
from sdlc_auth.adk import USER_TOKEN_STATE_KEY, reset_request_token, set_request_token

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

_USER_PATH = re.compile(r"^(/(?:dev/)?apps/[^/]+/users/)([^/]+)(/.*)?$")
# /dev routes the chat UI needs; everything else under /dev is developer tooling.
_DEV_ALLOWED = re.compile(r"^/dev/apps/[^/]+/(build_graph|build_graph_image|graph|users/.+)$")
_DEV_OWN_TRACE = re.compile(r"^/dev/apps/([^/]+)/debug/trace/session/([^/]+)$")
# Listings the dev UI requests when it loads: answer with an empty result instead of 403.
_DEV_EMPTY_LISTINGS = re.compile(
    r"^/dev/apps/[^/]+/(eval_sets|eval-sets|eval_results|eval-results|tests|builder)$"
)
_RUN_PATHS = {"/run", "/run_sse"}
_MAX_RUN_BODY = 10 * 1024 * 1024


class EntraUserBindingMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        verifier: TokenVerifier,
        *,
        token_header: str = "x-forwarded-access-token",  # noqa: S107 (header name)
        public_paths: frozenset[str] = frozenset({"/healthz"}),
        dev_tools: bool = False,
    ):
        self.app = app
        self.verifier = verifier
        self.token_header = token_header.lower().encode()
        self.public_paths = public_paths
        self.dev_tools = dev_tools

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            # Not bound to the user yet (user_id arrives as a query parameter): refuse.
            return await send({"type": "websocket.close", "code": 1008})
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if scope["path"] in self.public_paths:
            return await self.app(scope, receive, send)

        token = self._extract_token(scope)
        access = await self.verifier.load_access_token(token) if token else None
        if access is None:
            return await _respond(
                send,
                401,
                {"detail": "sign-in required"},
                [(b"www-authenticate", b'Bearer realm="sdlc"')],
            )
        try:
            oid = principal_from_claims(access.claims).oid
        except ValueError:
            return await _respond(send, 401, {"detail": "not a user token"})

        scope = dict(scope)
        if scope["path"].startswith("/dev/") and not self.dev_tools:
            refusal = await self._dev_route_refusal(scope, oid)
            if refusal:
                status, payload = refusal
                return await _respond(send, status, payload)
        bound_path = _bind_path(scope["path"], oid)
        if bound_path != scope["path"]:
            scope["path"] = bound_path
            scope["raw_path"] = bound_path.encode()
        if scope["method"] == "POST" and scope["path"] in _RUN_PATHS:
            body = await _read_body(receive, _MAX_RUN_BODY)
            if body is None:
                return await _respond(send, 413, {"detail": "request body too large"})
            body = _bind_run_body(body, oid)
            scope["headers"] = [
                (k, v) for k, v in scope["headers"] if k.lower() != b"content-length"
            ] + [(b"content-length", str(len(body)).encode())]
            receive = _replay(body, receive)

        reset = set_request_token(token)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_request_token(reset)

    async def _dev_route_refusal(self, scope: Scope, oid: str) -> tuple[int, Any] | None:
        """None if the /dev request may proceed, else (status, body) to answer instead."""
        path, method = scope["path"], scope["method"]
        if _DEV_ALLOWED.match(path) and method == "GET":
            return None
        trace = _DEV_OWN_TRACE.match(path)
        if trace and method == "GET":
            owned = await self._owns_session(scope, trace.group(1), trace.group(2), oid)
            return None if owned else (404, {"detail": "Session not found"})
        if _DEV_EMPTY_LISTINGS.match(path) and method == "GET":
            return 200, []
        return 403, {"detail": "developer tools are disabled"}

    async def _owns_session(self, scope: Scope, app_name: str, session_id: str, oid: str) -> bool:
        """Ask the ADK app whether the session exists under this user (internal subrequest)."""
        path = f"/apps/{app_name}/users/{oid}/sessions/{session_id}"
        sub_scope = {
            **scope,
            "method": "GET",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
        }
        status = 500

        async def receive() -> Message:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]

        await self.app(sub_scope, receive, send)
        return status == 200

    def _extract_token(self, scope: Scope) -> str | None:
        forwarded = bearer = None
        for key, value in scope.get("headers", []):
            name = key.lower()
            if name == self.token_header:
                forwarded = value.decode("latin-1").strip()
            elif name == b"authorization":
                raw = value.decode("latin-1")
                if raw[:7].lower() == "bearer ":
                    bearer = raw[7:].strip()
        return forwarded or bearer or None


def _bind_path(path: str, oid: str) -> str:
    match = _USER_PATH.match(path)
    if not match:
        return path
    return f"{match.group(1)}{oid}{match.group(3) or ''}"


def _bind_run_body(body: bytes, oid: str) -> bytes:
    try:
        payload = json.loads(body or b"{}")
    except ValueError:
        return body  # let ADK reject malformed JSON
    if not isinstance(payload, dict):
        return body
    # ADK's request model accepts snake_case and camelCase (alias wins when both are present);
    # the dev UI sends camelCase. Drop both spellings and set the alias.
    payload.pop("user_id", None)
    payload.pop("userId", None)
    payload["userId"] = oid
    for key in ("state_delta", "stateDelta"):
        state_delta = payload.get(key)
        if isinstance(state_delta, dict):
            state_delta.pop(
                USER_TOKEN_STATE_KEY, None
            )  # tokens only come from the validated header
    return json.dumps(payload).encode()


async def _read_body(receive: Receive, limit: int) -> bytes | None:
    chunks, size = [], 0
    while True:
        message = await receive()
        if message["type"] != "http.request":
            break
        chunk = message.get("body", b"")
        size += len(chunk)
        if size > limit:
            return None
        chunks.append(chunk)
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


def _replay(body: bytes, receive: Receive) -> Receive:
    sent = False

    async def replay() -> Message:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()  # later calls: disconnect monitoring

    return replay


async def _respond(send: Send, status: int, payload: Any, extra_headers=()) -> None:
    body = json.dumps(payload).encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
        *extra_headers,
    ]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})
