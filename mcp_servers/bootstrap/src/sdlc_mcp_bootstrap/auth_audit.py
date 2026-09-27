"""Audit rejected authentication (HTTP 401/403 on the MCP endpoint) to `sdlc.audit`.

Token validation happens in fastmcp's auth layer, before the policy middleware, so a rejected
request never produces a `tool_call` record. This ASGI middleware watches responses on the MCP
path and writes an `event: auth_failure` record for 401/403.

The reason is classified from the token's UNVERIFIED claims (e.g. expired, wrong tenant, wrong
audience); those claims are reported under `claimed` because a rejected token proves nothing.
The raw token is never logged, only a short SHA-256 fingerprint for correlation.
"""

import base64
import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from sdlc_config import ConfigStore

audit_log = logging.getLogger("sdlc.audit")


def _b64json(segment: str) -> dict | None:
    try:
        padded = segment + "=" * (-len(segment) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded))
        return value if isinstance(value, dict) else None
    except (ValueError, json.JSONDecodeError):
        return None


def classify(authorization: str | None, store: ConfigStore) -> tuple[str, dict, str | None]:
    """(reason, unverified claims subset, token fingerprint) for a rejected request."""
    if not authorization:
        return "missing_token", {}, None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return "malformed_token", {}, None
    fingerprint = "sha256:" + hashlib.sha256(token.encode()).hexdigest()[:16]
    parts = token.split(".")
    claims = _b64json(parts[1]) if len(parts) == 3 else None
    if claims is None:
        return "malformed_token", {}, fingerprint
    claimed = {
        k: claims.get(k)
        for k in ("oid", "preferred_username", "tid", "aud", "exp", "iss")
        if claims.get(k) is not None
    }
    platform = store.current().platform
    exp = claims.get("exp")
    if isinstance(exp, int | float) and exp < time.time():
        reason = "expired"
    elif claims.get("tid") != platform.tenant_id:
        reason = "wrong_tenant"
    elif claims.get("iss") != platform.issuer:
        reason = "wrong_issuer"
    elif claims.get("aud") not in platform.audience:
        reason = "wrong_audience"
    elif not set(str(claims.get("scp", "")).split()) >= set(platform.required_scopes):
        reason = "missing_scope"
    else:
        reason = "invalid_token"  # e.g. bad signature, app-only token, unknown signing key
    return reason, claimed, fingerprint


class AuthFailureAuditMiddleware:
    def __init__(self, app, store: ConfigStore, path_prefix: str = "/mcp"):
        self.app = app
        self.store = store
        self.path_prefix = path_prefix

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(self.path_prefix):
            return await self.app(scope, receive, send)
        status: dict[str, Any] = {}

        async def watch(message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        await self.app(scope, receive, watch)
        if status.get("code") in (401, 403):
            self._audit(scope, status["code"])

    def _audit(self, scope, code: int) -> None:
        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])
        }
        reason, claimed, fingerprint = classify(headers.get("authorization"), self.store)
        client = scope.get("client") or ("", 0)
        forwarded = headers.get("cf-connecting-ip") or headers.get("x-forwarded-for", "")
        record = {
            "event": "auth_failure",
            "ts": datetime.now(UTC).isoformat(),
            "status": code,
            "reason": reason,
            "method": scope.get("method"),
            "path": scope.get("path"),
            "client_ip": forwarded.split(",")[0].strip() or client[0],
            "user_agent": headers.get("user-agent", "")[:120],
            "token_fingerprint": fingerprint,
            "claimed": claimed,  # UNVERIFIED: taken from a token that was rejected
            "config_version": self.store.current().version,
        }
        audit_log.info(json.dumps(record, separators=(",", ":"), default=str))
