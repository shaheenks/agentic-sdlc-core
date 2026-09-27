"""Authorization decisions for MCP tools. Pure functions over an EffectivePolicy.

Deny by default: a tool call is allowed only if the tool is granted, not denied, and every
constrained argument is present with an allowed value. Each decision names the rule behind it
for the audit log.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from sdlc_config import EffectivePolicy

DEFAULT_DENY = "default-deny"


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str  # human-readable; safe to return to the caller
    matched_rule: str  # config rule (or "default-deny") for the audit log


def visible_tools(policy: EffectivePolicy, names: Iterable[str]) -> list[str]:
    """The subset of registered tool names this user may see (tools/list)."""
    return [name for name in names if policy.allows(name)]


def authorize(policy: EffectivePolicy, tool: str, arguments: Mapping[str, Any] | None) -> Decision:
    arguments = arguments or {}
    if tool in policy.denied:
        rule = policy.denied[tool][0]
        return Decision(False, f"tool '{tool}' is denied by policy", rule)
    permission = policy.tools.get(tool)
    if permission is None:
        return Decision(False, f"tool '{tool}' is not granted to you", DEFAULT_DENY)
    granted_by = permission.allowed_by[0]
    if permission.constraints:
        limits_rule = ", ".join(permission.constraint_sources)
        for arg, allowed_values in sorted(permission.constraints.items()):
            value = arguments.get(arg)
            if value is None:
                return Decision(
                    False, f"argument '{arg}' is required by policy for '{tool}'", limits_rule
                )
            if not isinstance(value, str) or value not in allowed_values:
                return Decision(
                    False,
                    f"{arg}={value!r} is not allowed for '{tool}' "
                    f"(allowed: {', '.join(sorted(allowed_values))})",
                    limits_rule,
                )
        return Decision(True, "allowed within argument limits", f"{granted_by}; {limits_rule}")
    return Decision(True, "allowed", granted_by)


from sdlc_policy.ratelimit import RateLimiter  # noqa: E402 (needs Decision)

__all__ = ["DEFAULT_DENY", "Decision", "RateLimiter", "authorize", "visible_tools"]
