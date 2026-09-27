"""Policy middleware: authentication check, RBAC (tools/list + tools/call) and audit.

- tools/list: only tools the caller's EffectivePolicy allows (deny by default).
- tools/call: authorize the tool AND its arguments (sdlc_policy.authorize) before it runs.
  A call without a validated token is refused even if it reached the server some other way
  (e.g. a non-HTTP transport).
- `sdlc.audit` JSON lines, one `event` per record, all carrying `request_id`:
    tool_call     oid, teams, roles, tool, args hash, decision, matched rule, outcome, and for
                  failures error_type + error (up to 500 chars)
    tools_list    who listed tools, visible names, hidden count
    skill_access  load_skill decisions: skill, allow/deny, matched rule and the reason
                  (the caller only ever sees "unknown skill" for a denial)
    skills_list   visible skill names, hidden count
  Rejected tokens (HTTP 401) are audited as `auth_failure` by auth_audit.py.
- Unexpected exceptions are also logged with their traceback to `sdlc.mcp`, tagged with the same
  request_id, so an audit line leads straight to the stack trace.
"""

import hashlib
import json
import logging
import time
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext
from sdlc_auth import GroupResolver
from sdlc_config import ConfigStore, PolicyCache, SkillDecision
from sdlc_policy import authorize

from sdlc_mcp_bootstrap.identity import (
    Identity,
    current_principal,
    remember_identity,
    resolve_identity,
)

audit_log = logging.getLogger("sdlc.audit")
server_log = logging.getLogger("sdlc.mcp")

ERROR_TEXT_LIMIT = 500


def args_hash(arguments: dict | None) -> str:
    """Hash, not raw values: arguments may contain sensitive data."""
    canonical = json.dumps(arguments or {}, sort_keys=True, default=str, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()[:16]


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def emit(record: dict) -> None:
    audit_log.info(json.dumps(record, separators=(",", ":"), default=str))


def _who(identity: Identity) -> dict:
    return {
        "request_id": identity.request_id,
        "oid": identity.principal.oid,
        "upn": identity.principal.upn,
        "teams": sorted(identity.policy.teams),
        "roles": sorted(identity.policy.roles),
        "config_version": identity.snapshot.version,
    }


def audit_skill_access(identity: Identity, skill: str, decision: SkillDecision) -> None:
    emit(
        {
            "event": "skill_access",
            "ts": datetime.now(UTC).isoformat(),
            **_who(identity),
            "skill": skill,  # skill names are identifiers, not user data
            "decision": "allow" if decision.allowed else "deny",
            "matched_rule": decision.matched_rule,
            "reason": decision.reason,
        }
    )


def audit_skills_list(identity: Identity, visible: Iterable[str], hidden_count: int) -> None:
    emit(
        {
            "event": "skills_list",
            "ts": datetime.now(UTC).isoformat(),
            **_who(identity),
            "visible": sorted(visible),
            "hidden_count": hidden_count,  # names of hidden skills are not disclosed
        }
    )


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

    async def _identity(self, request_id: str) -> Identity | None:
        principal = current_principal()
        if principal is None:
            return None
        snapshot = self._store.current()  # one snapshot for the whole request
        identity = await resolve_identity(
            principal, snapshot, self._group_resolver, self._cache, request_id
        )
        await remember_identity(identity)
        return identity

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        started, request_id = time.perf_counter(), new_request_id()
        tools = await call_next(context)
        identity = await self._identity(request_id)
        record = {"event": "tools_list", "ts": datetime.now(UTC).isoformat()}
        if identity is None:
            visible = []
            record.update(
                request_id=request_id,
                oid=None,
                upn=None,
                outcome="denied_unauthenticated",
                config_version=self._store.current().version,
            )
        else:
            visible = [tool for tool in tools if identity.policy.allows(tool.name)]
            record.update(**_who(identity), outcome="ok")
        record.update(
            visible=sorted(tool.name for tool in visible),
            hidden_count=len(tools) - len(visible),  # names of hidden tools are not disclosed
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        emit(record)
        return visible

    @staticmethod
    def _record_unexpected(record: dict, tool: str, request_id: str, error: BaseException) -> None:
        record.update(
            outcome="error",
            error_type=f"{type(error).__module__}.{type(error).__qualname__}",
            error=str(error)[:ERROR_TEXT_LIMIT],
        )
        server_log.error(
            "tool '%s' failed request_id=%s",
            tool,
            request_id,
            exc_info=(type(error), error, error.__traceback__),
        )

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        started, request_id = time.perf_counter(), new_request_id()
        tool, arguments = context.message.name, context.message.arguments
        record = {
            "event": "tool_call",
            "ts": datetime.now(UTC).isoformat(),
            "request_id": request_id,
            "tool": tool,
            "args_hash": args_hash(arguments),
            "oid": None,
            "upn": None,
            "teams": [],
            "roles": [],
            "config_version": self._store.current().version,
        }
        try:
            identity = await self._identity(request_id)
            if identity is None:
                record.update(
                    decision="deny",
                    matched_rule="unauthenticated",
                    outcome="denied_unauthenticated",
                )
                raise ToolError("authentication required")
            record.update(_who(identity))
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
            # fastmcp re-raises unexpected tool exceptions as ToolError; the original is the cause
            cause = e.__cause__ or e.__context__
            if cause is not None and not isinstance(cause, ToolError):
                self._record_unexpected(record, tool, request_id, cause)
            else:
                record.setdefault("outcome", "tool_error")
                record.update(error_type="ToolError", error=str(e)[:ERROR_TEXT_LIMIT])
            raise
        except Exception as e:
            self._record_unexpected(record, tool, request_id, e)
            raise
        finally:
            record["duration_ms"] = round((time.perf_counter() - started) * 1000, 1)
            emit(record)
