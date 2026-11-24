"""The request path shared by MCP and the HTTP API: who is calling, what they may use, and one audited
decision per call (FR-AUTHZ-002, FR-AUTHZ-003, FR-AUTHZ-005, NFR-AUD-001)."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sdlc_config_store import Bundle, ConfigStore
from sdlc_directory import Memberships, memberships
from sdlc_identity import GoogleTokens, Identity, IdentitySettings, identify
from sdlc_logging import audit
from sdlc_policy import EffectivePolicy, RateLimiter, effective_policy

from user_agent_mcp.artifacts import ArtifactStore
from user_agent_mcp.connections import ConnectionStore
from user_agent_mcp.errors import ToolError
from user_agent_mcp.knowledge import KnowledgeClient
from user_agent_mcp.settings import Settings
from user_agent_mcp.tools import TOOLS, Tool

LABEL = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")
RUN_HEADER, STEP_HEADER = "x-sdlc-run-id", "x-sdlc-step"
# The team a run is for, set by the declared caller from the session or run (FR-KNOW-004, DEC-0011).
TEAM_HEADER = "x-sdlc-team"


@dataclass(frozen=True)
class Caller:
    identity: Identity
    memberships: Memberships
    policy: EffectivePolicy
    bundle: Bundle
    run_id: str | None = None
    step: str | None = None

    def audit_fields(self) -> dict[str, Any]:
        """Who, through which surface, under which configuration; never argument values or the email."""
        fields = {
            "user_id": self.identity.user_id,
            "surface": self.identity.surface,
            "caller": self.identity.caller,
            "config_version": self.bundle.version,
        }
        if self.policy.team:
            fields["team"] = self.policy.team
        if self.run_id:
            fields["run_id"] = self.run_id
        if self.step:
            fields["step"] = self.step
        return fields


def _label(headers: Mapping[str, str], name: str) -> str | None:
    value = headers.get(name)
    return value if value and LABEL.match(value) else None


class Platform:
    def __init__(
        self,
        settings: Settings,
        store: ConfigStore,
        tokens: GoogleTokens,
        limiter: RateLimiter,
        artifacts: ArtifactStore,
        connections: ConnectionStore,
        knowledge: KnowledgeClient | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.tokens = tokens
        # A forwarding service account's ID token must be minted for this server.
        self.audiences = frozenset({settings.public_url, f"{settings.public_url}/mcp"})
        self.limiter = limiter
        self.artifacts = artifacts
        self.connections = connections
        self.knowledge = knowledge

    async def identify(self, headers: Mapping[str, str]) -> tuple[Identity, Bundle]:
        """The user of a request under the active bundle's identity mode (DEC-0010). `headers` must look
        names up case-insensitively. Raises sdlc_identity.Rejected or sdlc_config_store.ConfigUnavailable."""
        bundle = await self.store.acurrent()
        settings = IdentitySettings.from_config(bundle.config)
        identity = await identify(headers, settings, self.tokens, env=self.settings.env, audiences=self.audiences)
        return identity, bundle

    def team_allowed(self, identity: Identity, bundle: Bundle, headers: Mapping[str, str]) -> bool:
        """A run's team, when its caller names one, must be one of the user's teams."""
        team = headers.get(TEAM_HEADER)
        return team is None or team in memberships(bundle.config, identity.email).teams

    async def caller(self, identity: Identity, bundle: Bundle, headers: Mapping[str, str]) -> Caller:
        """The user's effective policy: in their own runs, or in the run of the team the caller names (the
        intersection with the team's grants). `team_allowed` has been checked before."""
        member = memberships(bundle.config, identity.email)
        team = headers.get(TEAM_HEADER) or None
        policy = effective_policy(bundle.config, bundle.version, identity.surface, member, team)
        return Caller(identity, member, policy, bundle, _label(headers, RUN_HEADER), _label(headers, STEP_HEADER))

    def visible_tools(self, caller: Caller, channel: str) -> list[Tool]:
        tools = [t for name, t in TOOLS.items() if caller.policy.authorize(name).allowed]
        if channel == "mcp":
            tools = [t for t in tools if not t.http_only]
        audit("tool.list", channel=channel, count=len(tools), **caller.audit_fields())
        return tools

    async def invoke(self, caller: Caller, name: str, args: dict[str, Any], channel: str) -> dict[str, Any]:
        """Authorize, rate limit, run and audit one call. Raises ToolError."""
        fields = {"channel": channel, "tool": name, **caller.audit_fields()}
        tool = TOOLS.get(name)
        decision = caller.policy.authorize(name)
        if tool is None or (channel == "mcp" and tool.http_only):
            decision_reason = "unknown_tool"
        elif not decision.allowed:
            decision_reason = decision.reason
        else:
            decision_reason = None
        if decision_reason is not None:
            audit("tool.call", decision="deny", rule=decision.rule, reason=decision_reason, **fields)
            raise ToolError("not_allowed", f"{name} is not available to you here")
        limit = self.limiter.check(
            caller.bundle.config, caller.identity.user_id, caller.memberships, caller.policy.team
        )
        if not limit.allowed:
            audit("tool.call", decision="deny", rule=limit.rule, reason=limit.reason, **fields)
            raise ToolError("rate_limited", "too many tool calls; try again in a minute")
        try:
            result = await tool.handler(self, caller, args if isinstance(args, dict) else {})
        except ToolError as exc:
            audit("tool.call", decision="allow", rule=decision.rule, outcome=exc.code, **fields)
            raise
        audit("tool.call", decision="allow", rule=decision.rule, outcome="ok", write=tool.write, **fields)
        return result
