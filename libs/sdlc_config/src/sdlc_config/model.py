"""Immutable, validated view of the config. One Snapshot per config version."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
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
    embedding_model: str = "gemini-embedding-2"
    authority_host: str = "https://login.microsoftonline.com"  # Entra login host (E7)
    graph_host: str = "https://graph.microsoft.com"  # Microsoft Graph host (E7)
    embedding_dimensions: int = 768
    graph_model: str = ""  # knowledge.graph.model; empty = graph extraction not configured
    graph_relation_types: tuple[str, ...] = ()
    graph_thinking_level: str = ""  # "" = the model's default
    default_calls_per_minute: int | None = None  # defaults/rate_limit (None = no baseline)

    def classification_rank(self, level: str) -> int:
        """Position of a level in classification_levels (0 = least sensitive)."""
        return self.classification_levels.index(level)


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
    skills_allow: frozenset[str] = frozenset()  # global skill names, "tag:<tag>" or "*"
    max_classification: str | None = None  # data ceiling granted by this role (Stage 5)


@dataclass(frozen=True)
class SkillDef:
    """A skill package. `team` is set for team add-ons (visible to that team's members only)."""

    name: str
    description: str
    instructions: str
    path: str  # e.g. "skills/core/write-user-story"
    source: str  # config rule that declares it, e.g. "skills.yaml#skills/write-user-story"
    team: str | None = None
    tags: frozenset[str] = frozenset()
    access_roles: frozenset[str] = frozenset()  # empty = no role restriction
    access_teams: frozenset[str] = frozenset()  # empty = no team restriction


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
    addon_skills: tuple[str, ...] = ()  # names of this team's add-on skills (in Snapshot.skills)
    instructions: str | None = None  # AGENT_ADDENDUM text appended to the agent prompt
    instructions_source: str | None = None  # e.g. "skills/teams/payments/AGENT_ADDENDUM.md"
    context: Mapping[str, str] = field(default_factory=dict)
    # per-user calls per minute: "*" = all tools, otherwise a tool name (policy/limits)
    limits: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceDef:
    """A knowledge source. Read access is granted ONLY by its access block."""

    id: str
    source: str  # e.g. "sources/payments-code.yaml"
    owner_team: str
    type: str
    location: str  # relative to the repo root, or absolute
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    classification: str
    classification_rank: int
    chunking: Mapping[str, object]
    graph_enabled: bool = False
    entity_types: tuple[str, ...] = ()
    relation_types: tuple[str, ...] = ()  # resolved: the source's list or the platform default
    access_teams: frozenset[str] = frozenset()
    access_roles: frozenset[str] = frozenset()
    access_groups: frozenset[str] = frozenset()
    description: str = ""


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
    skills: Mapping[str, SkillDef] = field(default_factory=dict)  # global + team add-ons
    sources: Mapping[str, SourceDef] = field(default_factory=dict)
    # E3: user object IDs (lower-case) denied on every request -> reason (env/<env>/blocked.yaml)
    blocked: Mapping[str, str] = field(default_factory=dict)
    # Every file this version was built from, repo-relative (config/..., skills/...) -> sha256.
    # sdlc-config compile copies exactly these into a bundle.
    files: Mapping[str, str] = field(default_factory=dict)
