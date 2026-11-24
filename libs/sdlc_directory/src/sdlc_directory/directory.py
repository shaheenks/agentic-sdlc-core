"""Team roles and user groups of one user, from the active configuration."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Memberships:
    teams: Mapping[str, frozenset[str]] = field(default_factory=dict)  # team id -> its roles for this user
    user_groups: frozenset[str] = frozenset()

    def describe(self) -> dict[str, Any]:
        return {"teams": {t: sorted(r) for t, r in sorted(self.teams.items())}, "user_groups": sorted(self.user_groups)}


def memberships(config: Mapping[str, Any], email: str) -> Memberships:
    """What `members` in the compiled configuration gives this email ({email: {teams: {team: [roles]},
    user_groups: [...]}}); a user who is not listed is in no team and no user group. Teams, roles and user
    groups that are no longer declared count for nothing."""
    entry = (config.get("members") or {}).get(email.lower()) or {}
    declared_teams = config.get("teams") or {}
    declared_groups = config.get("user_groups") or {}
    teams: dict[str, frozenset[str]] = {}
    for team, roles in (entry.get("teams") or {}).items():
        known = frozenset(roles) & frozenset((declared_teams.get(team) or {}).get("roles") or ())
        if known:
            teams[team] = known
    user_groups = frozenset(g for g in entry.get("user_groups") or () if g in declared_groups)
    return Memberships(teams, user_groups)
