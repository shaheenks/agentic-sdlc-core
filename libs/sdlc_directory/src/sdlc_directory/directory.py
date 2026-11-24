"""Team roles and user groups from group membership and the active configuration."""

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from sdlc_directory.groups import CloudIdentityGroups, GroupLookup, StaticGroups

STATIC = "static"


@dataclass(frozen=True)
class Memberships:
    teams: Mapping[str, frozenset[str]] = field(default_factory=dict)  # team id -> its roles for this user
    user_groups: frozenset[str] = frozenset()

    def describe(self) -> dict[str, Any]:
        return {"teams": {t: sorted(r) for t, r in sorted(self.teams.items())}, "user_groups": sorted(self.user_groups)}


def configured_groups(config: Mapping[str, Any]) -> frozenset[str]:
    """Every group email configuration maps to a team role or a user group."""
    groups: set[str] = set()
    for team in (config.get("teams") or {}).values():
        for emails in (team.get("roles") or {}).values():
            groups.update(e.lower() for e in emails)
    for user_group in (config.get("user_groups") or {}).values():
        groups.update(e.lower() for e in user_group.get("groups") or ())
    return frozenset(groups)


def resolve(config: Mapping[str, Any], groups: frozenset[str]) -> Memberships:
    """Team roles and user groups given the configured groups the user is in."""
    teams: dict[str, frozenset[str]] = {}
    for team_id, team in (config.get("teams") or {}).items():
        roles = frozenset(r for r, emails in (team.get("roles") or {}).items() if groups & {e.lower() for e in emails})
        if roles:
            teams[team_id] = roles
    user_groups = frozenset(
        ug_id
        for ug_id, ug in (config.get("user_groups") or {}).items()
        if groups & {e.lower() for e in ug.get("groups") or ()}
    )
    return Memberships(teams, user_groups)


class Directory:
    """`memberships(email, config)`. The group lookup follows `identity.directory` in the active
    configuration; `cloud_lookup` builds the Cloud Identity client, once per mode."""

    def __init__(self, cloud_lookup: Callable[[str, int], GroupLookup] | None = None) -> None:
        self._cloud_lookup = cloud_lookup or _cloud_identity
        self._lookups: dict[tuple, GroupLookup] = {}

    def _lookup(self, config: Mapping[str, Any]) -> GroupLookup:
        settings = (config.get("identity") or {}).get("directory") or {}
        mode = settings.get("mode", STATIC)
        if mode == STATIC:
            return StaticGroups(config.get("directory_users") or {})
        key = (mode, int(settings.get("cache_seconds", 300)))
        if key not in self._lookups:
            self._lookups[key] = self._cloud_lookup(*key)
        return self._lookups[key]

    async def memberships(self, email: str, config: Mapping[str, Any]) -> Memberships:
        candidates = configured_groups(config)
        if not candidates:
            return Memberships()
        groups = await self._lookup(config).groups_of(email, candidates)
        return resolve(config, groups)


def _cloud_identity(mode: str, cache_seconds: int) -> GroupLookup:
    return CloudIdentityGroups(
        mode=mode, cache_seconds=cache_seconds, quota_project=os.environ.get("GOOGLE_CLOUD_QUOTA_PROJECT") or None
    )
