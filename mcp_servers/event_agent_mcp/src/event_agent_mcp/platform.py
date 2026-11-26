"""The request path: the system identity, the run it calls for, what it may use, and one audited decision per call
(FR-IDN-004, FR-AGT-004, FR-TRIG-003, NFR-OBS-003, NFR-AUD-001).

Every request names the run's team, the subscription that started the run and the event's metadata in headers set
by the event agents' runtime from the run's input. The team must be one the system identity acts for, and the
subscription must be declared and enabled: its `writes` are the only write tools the run may call, all without
approval (people approve by merging).
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sdlc_config_store import Bundle, ConfigStore
from sdlc_identity import GoogleTokens, IdentitySettings, SystemCaller, identify_system
from sdlc_logging import audit
from sdlc_policy import EffectivePolicy, NotATeamMember, system_policy

from event_agent_mcp.errors import ToolError
from event_agent_mcp.settings import Settings
from event_agent_mcp.tools import TOOLS, Tool
from event_agent_mcp.workspace import WorkspaceRunner

LABEL = re.compile(r"^[A-Za-z0-9._:/#@-]{1,200}$")
TEAM_HEADER, SUBSCRIPTION_HEADER, RUN_HEADER = "x-sdlc-team", "x-sdlc-subscription", "x-sdlc-run-id"
# The event's metadata, carried on every call and audit record of the run (FR-IDN-004, NFR-OBS-003).
EVENT_HEADERS = {
    "event_source": "x-sdlc-event-source",
    "event_type": "x-sdlc-event-type",
    "delivery_id": "x-sdlc-event-delivery",
    "subject": "x-sdlc-event-subject",
}


class RunRefused(Exception):
    """The request names no run the system identity may act in."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _label(headers: Mapping[str, str], name: str) -> str | None:
    value = headers.get(name)
    return value if value and LABEL.match(value) else None


@dataclass(frozen=True)
class Run:
    caller: SystemCaller
    team: str
    subscription_id: str
    subscription: Mapping[str, Any]
    policy: EffectivePolicy
    bundle: Bundle
    run_id: str
    event: Mapping[str, str]

    @property
    def writes(self) -> frozenset[str]:
        return frozenset(self.subscription.get("writes") or ())

    @property
    def limits(self) -> Mapping[str, Any]:
        return self.subscription.get("limits") or {}

    def audit_fields(self) -> dict[str, Any]:
        """Who, for which run and event, under which configuration; never argument values."""
        return {
            "caller": self.caller.account,
            "surface": self.caller.surface,
            "team": self.team,
            "subscription": self.subscription_id,
            "run_id": self.run_id,
            "config_version": self.bundle.version,
            **self.event,
        }


class Platform:
    def __init__(
        self, settings: Settings, store: ConfigStore, tokens: GoogleTokens, workspace: WorkspaceRunner | None = None
    ) -> None:
        self.settings = settings
        self.store = store
        self.tokens = tokens
        self.workspace = workspace
        self.audiences = frozenset({settings.public_url, f"{settings.public_url}/mcp"})

    async def identify(self, headers: Mapping[str, str]) -> tuple[SystemCaller, Bundle]:
        """Raises sdlc_identity.Rejected or sdlc_config_store.ConfigUnavailable."""
        bundle = await self.store.acurrent()
        settings = IdentitySettings.from_config(bundle.config)
        caller = await identify_system(headers, settings, self.tokens, env=self.settings.env, audiences=self.audiences)
        return caller, bundle

    def run(self, caller: SystemCaller, bundle: Bundle, headers: Mapping[str, str]) -> Run:
        """The run a request belongs to, or RunRefused."""
        team, sub_id, run_id = (_label(headers, h) for h in (TEAM_HEADER, SUBSCRIPTION_HEADER, RUN_HEADER))
        if not (team and sub_id and run_id):
            raise RunRefused("no_run")
        subscription = (bundle.config.get("subscriptions") or {}).get(sub_id)
        if not subscription or not subscription.get("enabled", True):
            raise RunRefused("unknown_subscription")
        try:
            policy = system_policy(bundle.config, bundle.version, caller.surface, team)
        except NotATeamMember:
            raise RunRefused("not_a_system_team") from None
        event = {k: v for k, h in EVENT_HEADERS.items() if (v := _label(headers, h))}
        return Run(caller, team, sub_id, subscription, policy, bundle, run_id, event)

    def _allowed(self, run: Run, name: str) -> tuple[bool, str, str]:
        """(allowed, rule, reason) for one tool in this run."""
        tool = TOOLS.get(name)
        decision = run.policy.authorize(name)
        if tool is None:
            return False, decision.rule, "unknown_tool"
        if not decision.allowed:
            return False, decision.rule, decision.reason
        if tool.write and name not in run.writes:
            return False, f"subscription:{run.subscription_id}", "write_not_declared"
        return True, decision.rule, ""

    def visible_tools(self, run: Run) -> list[Tool]:
        tools = [t for name, t in TOOLS.items() if self._allowed(run, name)[0]]
        audit("tool.list", channel="mcp", count=len(tools), **run.audit_fields())
        return tools

    async def invoke(self, run: Run, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Authorize, run and audit one call. Raises ToolError."""
        fields = {"channel": "mcp", "tool": name, **run.audit_fields()}
        allowed, rule, reason = self._allowed(run, name)
        if not allowed:
            audit("tool.call", decision="deny", rule=rule, reason=reason, **fields)
            raise ToolError("not_allowed", f"{name} is not available to this run")
        tool = TOOLS[name]
        try:
            result = await tool.handler(self, run, args if isinstance(args, dict) else {})
        except ToolError as exc:
            audit("tool.call", decision="allow", rule=rule, outcome=exc.code, write=tool.write, **fields)
            raise
        audit("tool.call", decision="allow", rule=rule, outcome="ok", write=tool.write, **fields)
        return result
