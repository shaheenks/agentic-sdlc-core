"""Immutable, validated view of the config. One Snapshot per config version."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class PlatformConfig:
    tenant_id: str
    issuer: str
    jwks_uri: str
    audience: tuple[str, ...]
    required_scopes: tuple[str, ...]
    classification_levels: tuple[str, ...]
    default_max_classification: str
    embedding_model: str = "gemini-embedding-2"
    authority_host: str = "https://login.microsoftonline.com"  # Entra login host (E7)
    embedding_dimensions: int = 768
    graph_model: str = ""  # knowledge.graph.model; empty = graph extraction not configured
    graph_relation_types: tuple[str, ...] = ()
    graph_thinking_level: str = ""  # "" = the model's default
    ocr_model: str = ""  # knowledge.ocr.model; empty = no model reading of PDF pages
    ocr_thinking_level: str = ""
    default_calls_per_minute: int | None = None  # defaults/rate_limit (None = no baseline)
    allowed_hosts: tuple[str, ...] = ()  # knowledge.allowed_hosts: remote source hosts (SSRF guard)
    keyword_search: bool = False  # knowledge.keyword_search: fuse full-text with vector (P11)
    team_skill_tags: frozenset[str] = frozenset()  # skills.team_tags: tags team add-ons may carry
    # flows.document (G7): lenses, max_lenses, max_llm_calls_per_reviewer, max_rereviews
    document_flow: Mapping[str, Any] = field(default_factory=dict)

    def classification_rank(self, level: str) -> int:
        """Position of a level in classification_levels (0 = least sensitive)."""
        return self.classification_levels.index(level)


@dataclass(frozen=True)
class UserMap:
    """Users added directly to teams/roles (env/<env>/users.yaml, git-ignored). Matched ONLY on
    the token's oid; emails are for people and for the oid lookup, never for authorization."""

    alias_by_oid: Mapping[str, str] = field(default_factory=dict)  # lower-cased oid -> alias
    email_by_alias: Mapping[str, str] = field(default_factory=dict)
    pending: tuple[str, ...] = ()  # aliases without an oid yet: they grant nothing
    default_team: Mapping[str, str] = field(default_factory=dict)  # alias -> team (G9, guidance)

    def alias_for(self, oid: str | None) -> str | None:
        return self.alias_by_oid.get(oid.lower()) if oid else None


@dataclass(frozen=True)
class IdentityRef:
    """Who a binding applies to: an Entra app role value, a user alias (users.yaml) or everyone
    (every signed-in user). Entra groups are not used (CH-0011)."""

    kind: str  # "app_role" | "user" | "everyone"
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
    user_connection: str | None = None  # credentials.user: connection the tool uses as the user


# Atlassian Cloud and Bitbucket Cloud tokens are used with the account email (HTTP Basic).
_NEEDS_USERNAME = {
    ("bitbucket", "cloud"),
    ("jira", "cloud"),
    ("confluence", "cloud"),
    ("atlassian", "cloud"),
}


@dataclass(frozen=True)
class ConnectionDef:
    """A system users connect their own account to (connections.yaml, version-01 M6)."""

    id: str
    provider: str  # github | bitbucket | jira | confluence | atlassian
    edition: str  # cloud | datacenter
    base_url: str  # API base URL, https, host in knowledge.allowed_hosts
    description: str = ""
    max_token_days: int = 90
    token_help: str = ""

    @property
    def needs_username(self) -> bool:
        return (self.provider, self.edition) in _NEEDS_USERNAME


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
    description: str = ""  # metadata.description: one line for the agent (G9)
    document_flow: Mapping[str, Any] = field(default_factory=dict)  # addons.flows.document (G7)


@dataclass(frozen=True)
class SourceDef:
    """A knowledge source. Read access is granted ONLY by its access block."""

    id: str
    source: str  # e.g. "sources/payments-code.yaml"
    owner_team: str
    type: str
    location: str  # relative to the repo root, or absolute (git: or an https URL)
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    classification: str
    classification_rank: int
    chunking: Mapping[str, object]
    ref: str | None = None  # git sources: commit, tag or branch
    # ("env" | "secret", name): a reference to the secret, never its value
    credentials: tuple[str, str] | None = None
    provider: str | None = None  # git over https: github | bitbucket-cloud | bitbucket-dc
    # type-specific settings (confluence: edition, space, cql, attachments)
    options: Mapping[str, object] = field(default_factory=dict)
    pdf_ocr: str = "none"  # spec.ingest.pdf.ocr: none | gemini (H10)
    pdf_max_mb: float = 50.0
    pdf_max_pages: int = 500
    graph_enabled: bool = False
    entity_types: tuple[str, ...] = ()
    relation_types: tuple[str, ...] = ()  # resolved: the source's list or the platform default
    access_teams: frozenset[str] = frozenset()
    access_roles: frozenset[str] = frozenset()
    access_everyone: bool = False  # access.everyone: every signed-in user
    description: str = ""


@dataclass(frozen=True)
class Snapshot:
    """One loaded config version. Take one per request; never mix two versions."""

    version: str
    env: str
    loaded_at: datetime
    platform: PlatformConfig
    roles: Mapping[str, RoleDef]
    bindings: tuple[RoleBinding, ...]
    tools: Mapping[str, ToolDef]
    teams: Mapping[str, TeamDef]
    skills: Mapping[str, SkillDef] = field(default_factory=dict)  # global + team add-ons
    sources: Mapping[str, SourceDef] = field(default_factory=dict)
    connections: Mapping[str, "ConnectionDef"] = field(default_factory=dict)
    users: UserMap = field(default_factory=UserMap)  # direct members (env/<env>/users.yaml)
    # E3: user object IDs (lower-case) denied on every request -> reason (env/<env>/blocked.yaml)
    blocked: Mapping[str, str] = field(default_factory=dict)
    # Every file this version was built from, repo-relative (config/..., skills/...) -> sha256.
    # sdlc-config compile copies exactly these into a bundle.
    files: Mapping[str, str] = field(default_factory=dict)

    @property
    def app_role_values(self) -> frozenset[str]:
        """Every Entra app role value the config grants something to."""
        refs = [b.ref for b in self.bindings]
        refs += [m.ref for team in self.teams.values() for m in team.membership]
        return frozenset(r.value for r in refs if r.kind == "app_role")
