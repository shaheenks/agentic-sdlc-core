"""Audit every tool call as one JSON line on the `sdlc.audit` logger.

Also the last line of defense for authentication: a tool call without a validated token is
rejected here even if it reached the server some other way (e.g. a non-HTTP transport).
Stage 3 adds the authorization decision + matched rule to each record.
"""

import hashlib
import json
import logging
import time
from datetime import UTC, datetime

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext
from sdlc_config import ConfigStore

from sdlc_mcp_bootstrap.identity import current_principal

audit_log = logging.getLogger("sdlc.audit")


def args_hash(arguments: dict | None) -> str:
    """Hash, not raw values: arguments may contain sensitive data."""
    canonical = json.dumps(arguments or {}, sort_keys=True, default=str, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()[:16]


class AuditMiddleware(Middleware):
    def __init__(self, store: ConfigStore):
        self._store = store

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        started = time.perf_counter()
        principal = current_principal()
        record = {
            "event": "tool_call",
            "ts": datetime.now(UTC).isoformat(),
            "tool": context.message.name,
            "args_hash": args_hash(context.message.arguments),
            "oid": principal.oid if principal else None,
            "upn": principal.upn if principal else None,
            "config_version": self._store.current().version,
        }
        try:
            if principal is None:
                record["outcome"] = "denied_unauthenticated"
                raise ToolError("authentication required")
            result = await call_next(context)
            record["outcome"] = "ok"
            return result
        except ToolError as e:
            record.setdefault("outcome", "tool_error")
            record["error"] = str(e)[:200]
            raise
        except Exception as e:
            record["outcome"] = "error"
            record["error"] = type(e).__name__
            raise
        finally:
            record["duration_ms"] = round((time.perf_counter() - started) * 1000, 1)
            audit_log.info(json.dumps(record, separators=(",", ":")))
