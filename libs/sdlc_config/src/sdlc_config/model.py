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
class IdentityRef:
    """Who a binding applies to: a group alias (groups.yaml), an Entra app role value, or
    everyone (every signed-in user)."""

    kind: str  # "group" | "app_role" | "everyone"
    value: str

    def __str__(self) -> str:
        return f"{self.kind}:{self.value}"


@dataclass(frozen=True)
class RoleBinding:
    """Grants roles to an identity. `rule` names where it is declared (for explain/audit)."""

    ref: IdentityRef
    roles: tuple[str, ...]
    rule: str  # e.g. "roles.yaml#bindings[0]" or "teams/payments.yaml#membership[1]"
    team: str | None = None  # set for team membership entries


@dataclass(frozen=True)
class RoleDef:
    name: str
    inherits: tuple[str, ...]
    tools_allow: frozenset[str]  # tool names or "*"
    tools_deny: frozenset[str]
    unconstrained: bool  # team argument limits don't apply to this role's grants


@dataclass(frozen=True)
class ToolDef:
    name: str
    server: str
    risk: str
    data_scoped: bool
    args: frozenset[str]  # arguments that team policies may constrain


@dataclass(frozen=True)
class TeamDef:
    name: str
    source: str  # e.g. "teams/payments.yaml"
    owners: tuple[str, ...]
    membership: tuple[RoleBinding, ...]
    tools_deny: frozenset[str]
    # tool -> arg -> allowed values
    constraints: Mapping[str, Mapping[str, frozenset[str]]]


@dataclass(frozen=True)
class Snapshot:
    """One loaded config version. Take one per request; never mix two versions."""

    version: str
    env: str
    loaded_at: datetime
    platform: PlatformConfig
    groups: GroupMap
    roles: Mapping[str, RoleDef]
    bindings: tuple[RoleBinding, ...]
    tools: Mapping[str, ToolDef]
    teams: Mapping[str, TeamDef]
