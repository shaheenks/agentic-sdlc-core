"""Immutable, validated view of the config. One Snapshot per config version."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PlatformConfig:
    tenant_id: str
    issuer: str
    jwks_uri: str
    audience: tuple[str, ...]
    required_scopes: tuple[str, ...]
    groups_overage_fallback: str  # "graph_transitive_member_of" | "none"
    groups_cache_ttl_seconds: int
    classification_levels: tuple[str, ...]
    default_max_classification: str


@dataclass(frozen=True)
class GroupMap:
    """Entra group object ID <-> alias. Group IDs appear only in env/<env>/groups.yaml."""

    alias_by_id: Mapping[str, str]  # lower-cased GUID -> alias

    def aliases_for(self, group_ids: Iterable[str]) -> tuple[tuple[str, ...], int]:
        """Map token group IDs to aliases. Returns (sorted aliases, count of unmapped IDs).

        Unmapped IDs are ignored for authorization; the count is only for diagnostics.
        """
        aliases, unmapped = set(), 0
        for gid in group_ids:
            alias = self.alias_by_id.get(gid.lower())
            if alias is None:
                unmapped += 1
            else:
                aliases.add(alias)
        return tuple(sorted(aliases)), unmapped


@dataclass(frozen=True)
class Snapshot:
    """One loaded config version. Take one per request; never mix two versions."""

    version: str
    env: str
    loaded_at: datetime
    platform: PlatformConfig
    groups: GroupMap
