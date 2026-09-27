"""Policy middleware: authentication check, RBAC (tools/list + tools/call) and audit.

- tools/list: only tools the caller's EffectivePolicy allows (deny by default).
- tools/call: authorize the tool AND its arguments (sdlc_policy.authorize) before it runs.
  A call without a validated token is refused even if it reached the server some other way
  (e.g. a non-HTTP transport).
- `sdlc.audit` JSON lines: `tool_call` (oid, teams, roles, tool, args hash, decision, matched
  rule, outcome, config version) and `tools_list` (who listed tools, visible names, hidden count).
  Rejected tokens (HTTP 401) are audited as `auth_failure` by auth_audit.py.
"""

import hashlib
import json
import logging
import time
from datetime import UTC, datetime

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext
from sdlc_auth import GroupResolver
from sdlc_config import ConfigStore, PolicyCache
from sdlc_policy import authorize

from sdlc_mcp_bootstrap.identity import current_principal, remember_identity, resolve_identity

audit_log = logging.getLogger("sdlc.audit")


def args_hash(arguments: dict | None) -> str:
    """Hash, not raw values: arguments may contain sensitive data."""
    canonical = json.dumps(arguments or {}, sort_keys=True, default=str, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()[:16]


class PolicyMiddleware(Middleware):
    def __init__(
        self,
        store: ConfigStore,
        group_resolver: GroupResolver | None = None,
        cache: PolicyCache | None = None,
    ):
        self._store = store
        self._group_resolver = group_resolver
        self._cache = cache or PolicyCache()

    async def _identity(self):
        principal = current_principal()
        if principal is None:
            return None
        snapshot = self._store.current()  # one snapshot for the whole request
        identity = await resolve_identity(principal, snapshot, self._group_resolver, self._cache)
        await remember_identity(identity)
        return identity

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        started = time.perf_counter()
        tools = await call_next(context)
        identity = await self._identity()
        record = {"event": "tools_list", "ts": datetime.now(UTC).isoformat()}
        if identity is None:
            visible = []
            record.update(
                oid=None,
                upn=None,
                outcome="denied_unauthenticated",
                config_version=self._store.current().version,
            )
        else:
            visible = [tool for tool in tools if identity.policy.allows(tool.name)]
            record.update(
                oid=identity.principal.oid,
                upn=identity.principal.upn,
                teams=sorted(identity.policy.teams),
                roles=sorted(identity.policy.roles),
                outcome="ok",
                config_version=identity.snapshot.version,
            )
        record.update(
            visible=sorted(tool.name for tool in visible),
            hidden_count=len(tools) - len(visible),  # names of hidden tools are not disclosed
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        audit_log.info(json.dumps(record, separators=(",", ":")))
        return visible

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        started = time.perf_counter()
        tool, arguments = context.message.name, context.message.arguments
        record = {
            "event": "tool_call",
            "ts": datetime.now(UTC).isoformat(),
            "tool": tool,
            "args_hash": args_hash(arguments),
            "oid": None,
            "upn": None,
            "teams": [],
            "roles": [],
            "config_version": self._store.current().version,
        }
        try:
            identity = await self._identity()
            if identity is None:
                record.update(
                    decision="deny",
                    matched_rule="unauthenticated",
                    outcome="denied_unauthenticated",
                )
                raise ToolError("authentication required")
            record.update(
                oid=identity.principal.oid,
                upn=identity.principal.upn,
                teams=sorted(identity.policy.teams),
                roles=sorted(identity.policy.roles),
                config_version=identity.snapshot.version,
            )
            decision = authorize(identity.policy, tool, arguments)
            record.update(
                decision="allow" if decision.allowed else "deny",
                matched_rule=decision.matched_rule,
            )
            if not decision.allowed:
                record.update(outcome="denied", reason=decision.reason)
                raise ToolError(f"not permitted: {decision.reason}")
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
