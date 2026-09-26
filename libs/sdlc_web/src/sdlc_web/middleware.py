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

_USER_PATH = re.compile(r"^(/apps/[^/]+/users/)([^/]+)(/.*)?$")
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
    ):
        self.app = app
        self.verifier = verifier
        self.token_header = token_header.lower().encode()
        self.public_paths = public_paths

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
    payload["user_id"] = oid
    state_delta = payload.get("state_delta")
    if isinstance(state_delta, dict):
        state_delta.pop(USER_TOKEN_STATE_KEY, None)  # tokens only come from the validated header
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


async def _respond(send: Send, status: int, payload: dict, extra_headers=()) -> None:
    body = json.dumps(payload).encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
        *extra_headers,
    ]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})
