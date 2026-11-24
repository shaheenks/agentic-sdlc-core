"""Effective policy and per-call decisions."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from sdlc_directory import Memberships

DEFAULT_DENY = "default-deny"


class NotATeamMember(Exception):
    """A team run was asked for a team the user is not in."""


@dataclass(frozen=True)
class Decision:
    allowed: bool
    rule: str
    reason: str = ""


def matches(to: Mapping[str, Any], memberships: Memberships) -> bool:
    """Whether a grant's `to` selector covers this user."""
    if to.get("everyone"):
        return True
    for entry in to.get("teams") or ():
        team, _, role = str(entry).partition(":")
        roles = memberships.teams.get(team)
        if roles and (not role or role in roles):
            return True
    return bool(memberships.user_groups & set(to.get("user_groups") or ()))


def _names_team(to: Mapping[str, Any], team: str) -> bool:
    return bool(to.get("everyone")) or any(str(e).partition(":")[0] == team for e in to.get("teams") or ())


@dataclass(frozen=True)
class EffectivePolicy:
    surface: str
    team: str | None
    config_version: str
    tools: Mapping[str, str]  # allowed tool -> the rule that allows it
    tool_groups: Mapping[str, str]  # allowed tool group -> the grant that allows it
    sources: Mapping[str, str] = field(default_factory=dict)  # readable knowledge source -> the grant (DEC-0011)

    def authorize(self, tool: str) -> Decision:
        rule = self.tools.get(tool)
        if rule is None:
            return Decision(False, DEFAULT_DENY, "not_allowed")
        return Decision(True, rule)

    def describe(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "team": self.team,
            "config_version": self.config_version,
            "tool_groups": sorted(self.tool_groups),
            "tools": sorted(self.tools),
            "sources": sorted(self.sources),
        }


def _granted(config: Mapping[str, Any], memberships: Memberships, team: str | None, kind: str) -> dict[str, str]:
    """Tool group or source (`kind` is the grant's key) -> first grant that gives it to this user (and, for a
    team run, to the team)."""
    personal: dict[str, str] = {}
    team_wide: set[str] = set()
    for grant in config.get("grants") or ():
        to = grant.get("to") or {}
        for item in grant.get(kind) or ():
            if matches(to, memberships):
                personal.setdefault(item, f"grant:{grant['id']}")
            if team is not None and _names_team(to, team):
                team_wide.add(item)
    if team is None:
        return personal
    return {item: rule for item, rule in personal.items() if item in team_wide}


def effective_policy(
    config: Mapping[str, Any],
    config_version: str,
    surface: str,
    memberships: Memberships,
    team: str | None = None,
) -> EffectivePolicy:
    if team is not None and team not in memberships.teams:
        raise NotATeamMember(team)
    granted = _granted(config, memberships, team, "tool_groups")
    declared_sources = config.get("sources") or {}
    sources = {s: r for s, r in _granted(config, memberships, team, "sources").items() if s in declared_sources}
    surface_groups = set(((config.get("surfaces") or {}).get(surface) or {}).get("tool_groups") or ())
    tool_groups = {g: rule for g, rule in granted.items() if g in surface_groups}
    tools: dict[str, str] = {}
    declared = config.get("tool_groups") or {}
    for group, rule in sorted(tool_groups.items()):
        for tool in (declared.get(group) or {}).get("tools") or ():
            tools.setdefault(tool, f"{rule}/tool_group:{group}/surface:{surface}")
    return EffectivePolicy(surface, team, config_version, tools, tool_groups, sources)
