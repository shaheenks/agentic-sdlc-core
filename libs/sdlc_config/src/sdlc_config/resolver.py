"""Resolve a principal's identities into an EffectivePolicy (plan: resolution steps 1-5).

identities (group aliases + Entra app roles + the user alias from users.yaml, matched by oid)
  -> teams (membership) + global bindings -> SCOPED roles (CH-0009): a global binding gives a
     platform role; a team membership gives a role in that team only (`approver@payments`).
     `inherits` expands within the same scope. Platform roles count in every team.
  -> allowed tools (any held role allows, "*" = whole catalog) minus denies (role + team); deny
     wins
  -> argument limits: unioned across the teams whose roles grant the tool and that constrain it
     (for a tool a platform role grants: every member team that constrains it); tools granted by
     an `unconstrained` role get none. A team that grants nothing never widens or narrows a tool.
  -> skills (step 6): global skills granted by any held role (name, "tag:<tag>", "*") and, when
     the skill sets `access`, held by one of its roles or teams; plus member teams' add-on
     skills, whose `access` roles must be held in that team (or as platform roles). A "*" skill
     grant (admin) also covers every team's add-ons.
  -> agent context (step 8): member teams' instructions (AGENT_ADDENDUM) and context.
  -> data (step 7): allowed sources = sources whose `access` matches the caller's teams, roles
     (platform roles, or roles held in the source's owner team) or group aliases, or that set
     `everyone: true` (the ONLY grant for data; a source can have its own Entra group,
     independent of teams). The ceiling is PER SOURCE: the highest level among the platform
     roles and the roles held in the source's owner team (platform default otherwise).
     Postgres RLS enforces both on every query.
Every role, grant, deny and limit records the config rule it came from.
"""

import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from sdlc_config.model import IdentityRef, Snapshot

PLATFORM = None  # scope of roles from global bindings (roles.yaml, users.yaml `roles`)

Scope = str | None  # None = platform, else a team name


def scoped_name(scope: Scope, role: str) -> str:
    """How a held role is shown: `admin` (platform) or `approver@payments` (team)."""
    return role if scope is PLATFORM else f"{role}@{scope}"


@dataclass(frozen=True)
class ToolPermission:
    tool: str
    allowed_by: tuple[str, ...]  # e.g. "role:member@payments <- teams/payments.yaml#membership[0]"
    # arg -> allowed values; None = no limits
    constraints: Mapping[str, frozenset[str]] | None = None
    constraint_sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkillGrant:
    skill: str
    granted_by: tuple[str, ...]  # e.g. "role:member@payments <- ..." or "team:payments <- ..."
    team: str | None = None  # set for team add-ons


@dataclass(frozen=True)
class TeamInstructions:
    team: str
    source: str  # e.g. "skills/teams/payments/AGENT_ADDENDUM.md"
    text: str


@dataclass(frozen=True)
class EffectivePolicy:
    config_version: str
    group_aliases: tuple[str, ...]
    app_roles: tuple[str, ...]
    teams: Mapping[str, tuple[str, ...]]  # team -> membership rules that matched
    # held role, scoped ("admin", "approver@payments") -> reasons (binding/membership or inherits)
    roles: Mapping[str, tuple[str, ...]]
    tools: Mapping[str, ToolPermission]  # allowed tools only
    denied: Mapping[str, tuple[str, ...]] = field(default_factory=dict)  # tool -> deny rules
    skills: Mapping[str, SkillGrant] = field(default_factory=dict)  # visible skills only
    agent_instructions: tuple[TeamInstructions, ...] = ()
    context: Mapping[str, Mapping[str, str]] = field(default_factory=dict)  # team -> values
    data_sources: Mapping[str, tuple[str, ...]] = field(default_factory=dict)  # id -> grant rules
    # Highest ceiling over all scopes (shown to users); reads use the per-source ceilings.
    max_classification: str = "public"
    max_classification_rank: int = 0
    # Current classification rank of each granted source (from this config version).
    source_classification: Mapping[str, int] = field(default_factory=dict)
    # Ceiling (level name) per granted source: platform roles + roles held in its owner team.
    source_ceilings: Mapping[str, str] = field(default_factory=dict)
    source_ceiling_ranks: Mapping[str, int] = field(default_factory=dict)
    user: str | None = None  # users.yaml alias (direct member), matched by the token oid
    # Per-user calls per minute: scope ("*" = all tools, or a tool) -> (limit, rule it came from).
    # Most generous of the user's teams; "*" falls back to platform defaults/rate_limit.
    rate_limits: Mapping[str, tuple[int, str]] = field(default_factory=dict)
    # Allowed tools that read knowledge data (tools.yaml `data_scoped: true`).
    data_tools: tuple[str, ...] = ()
    # users.yaml default_team, only while the user is a member of it (G9; guidance, grants nothing)
    default_team: str | None = None
    # (scope, role) pairs behind `roles`, for checks that need the scope
    held_roles: frozenset[tuple[Scope, str]] = frozenset()

    @property
    def readable_sources(self) -> tuple[str, ...]:
        """Granted sources at or below the caller's ceiling FOR THAT SOURCE, by the CURRENT
        config. This is what the RLS context carries, so raising a source's classification takes
        effect on the next request without re-ingesting (rows keep their own stamp as a second
        check against the same per-source ceiling; a lowered classification applies once ingest
        re-stamps the rows: fail closed). A source without a known classification is not
        readable."""
        return tuple(
            sid
            for sid in sorted(self.data_sources)
            if self.source_classification.get(sid, 1 << 30)
            <= self.source_ceiling_ranks.get(sid, -1)
        )

    def roles_in(self, team: str | None) -> frozenset[str]:
        """Role names that count in `team`: platform roles plus roles held in that team."""
        return frozenset(r for s, r in self.held_roles if s is PLATFORM or s == team)

    def allows(self, tool: str) -> bool:
        return tool in self.tools

    def sees_skill(self, name: str) -> bool:
        return name in self.skills

    def _explain_data(self) -> dict:
        """Data view: `readable` lists only what the user can actually read, which needs both a
        grant within the ceiling AND a knowledge tool. A grant without such a tool (e.g. an
        `everyone: true` source for a user with only `signed-in`) is shown as such, not as
        readable."""
        data = {
            "sources": {sid: list(r) for sid, r in sorted(self.data_sources.items())},
            "max_classification": self.max_classification,
            "ceilings": dict(sorted(self.source_ceilings.items())),
            "tools": list(self.data_tools),
            "readable": list(self.readable_sources) if self.data_tools else [],
        }
        if self.readable_sources and not self.data_tools:
            data["note"] = (
                "granted, but no knowledge tool: "
                + ", ".join(self.readable_sources)
                + " cannot be read until a role grants search_knowledge or graph_query"
            )
        return data

    def explain(self) -> dict:
        """JSON-friendly view for whoami(explain) / config_explain / CLI."""
        return {
            "config_version": self.config_version,
            "group_aliases": list(self.group_aliases),
            "app_roles": list(self.app_roles),
            "user": self.user,
            "teams": {t: list(r) for t, r in sorted(self.teams.items())},
            "roles": {r: list(why) for r, why in sorted(self.roles.items())},
            "tools": {
                name: {
                    "allowed_by": list(p.allowed_by),
                    "constraints": (
                        {arg: sorted(v) for arg, v in p.constraints.items()}
                        if p.constraints
                        else None
                    ),
                    "constraint_sources": list(p.constraint_sources),
                }
                for name, p in sorted(self.tools.items())
            },
            "denied": {t: list(r) for t, r in sorted(self.denied.items())},
            "skills": {
                name: {"granted_by": list(g.granted_by), "team": g.team}
                for name, g in sorted(self.skills.items())
            },
            "data": self._explain_data(),
            "rate_limits": {
                scope: {"calls_per_minute": limit, "rule": rule}
                for scope, (limit, rule) in sorted(self.rate_limits.items())
            },
            "agent_context": {
                "instructions": [
                    {"team": i.team, "source": i.source} for i in self.agent_instructions
                ],
                "context": {t: dict(c) for t, c in sorted(self.context.items())},
                "default_team": self.default_team,
            },
        }


def resolve(
    snapshot: Snapshot,
    group_aliases: Iterable[str],
    app_roles: Iterable[str] = (),
    user: str | None = None,
) -> EffectivePolicy:
    """`user` is the caller's users.yaml alias (Snapshot.users.alias_for(oid)), if any."""
    aliases, roles_claim = tuple(sorted(set(group_aliases))), tuple(sorted(set(app_roles)))
    # Every resolved principal is a signed-in user, so `everyone` bindings always apply.
    ids = {IdentityRef("everyone", "*")}
    ids |= {IdentityRef("group", a) for a in aliases}
    ids |= {IdentityRef("app_role", r) for r in roles_claim}
    if user:
        ids.add(IdentityRef("user", user))

    # 1-3: teams and directly granted roles, each in its scope
    team_rules: dict[str, list[str]] = {}
    held: dict[tuple[Scope, str], list[str]] = {}
    for binding in snapshot.bindings:
        if binding.ref in ids:
            for role in binding.roles:
                held.setdefault((PLATFORM, role), []).append(binding.rule)
    for team in snapshot.teams.values():
        for member in team.membership:
            if member.ref in ids:
                team_rules.setdefault(team.name, []).append(member.rule)
                for role in member.roles:
                    held.setdefault((team.name, role), []).append(member.rule)

    # 4: expand inherits within each scope (the loader rejects cycles; `seen` guards anyway)
    pending, seen = list(held), set()
    while pending:
        scope, role = pending.pop()
        if (scope, role) in seen:
            continue
        seen.add((scope, role))
        for parent in snapshot.roles[role].inherits:
            reason = f"inherited from role:{scoped_name(scope, role)}"
            if reason not in held.setdefault((scope, parent), []):
                held[(scope, parent)].append(reason)
            pending.append((scope, parent))

    def origin(key: tuple[Scope, str]) -> str:
        return f"role:{scoped_name(*key)} <- {held[key][0]}"

    # 5: allowed tools, denies, argument limits
    catalog = snapshot.tools
    allowed_by: dict[str, list[str]] = {}
    unconstrained: set[str] = set()
    granting_teams: dict[str, set[str]] = {}
    platform_granted: set[str] = set()
    denied: dict[str, list[str]] = {}
    for key in sorted(held, key=lambda k: (k[0] or "", k[1])):
        scope, role = key
        definition = snapshot.roles[role]
        granted = catalog.keys() if "*" in definition.tools_allow else definition.tools_allow
        for tool in granted:
            if origin(key) not in allowed_by.setdefault(tool, []):
                allowed_by[tool].append(origin(key))
            if definition.unconstrained:
                unconstrained.add(tool)
            elif scope is PLATFORM:
                platform_granted.add(tool)
            else:
                granting_teams.setdefault(tool, set()).add(scope)
        for tool in definition.tools_deny:
            rule = f"role:{role} deny"
            if rule not in denied.setdefault(tool, []):
                denied[tool].append(rule)
    for team in team_rules:
        for tool in snapshot.teams[team].tools_deny:
            denied.setdefault(tool, []).append(f"{snapshot.teams[team].source}#policy/tools/deny")

    tools: dict[str, ToolPermission] = {}
    for tool, origins in sorted(allowed_by.items()):
        if tool in denied or tool not in catalog:
            continue
        limits: dict[str, set[str]] = {}
        sources: list[str] = []
        if tool not in unconstrained:
            limiting = set(team_rules) if tool in platform_granted else set()
            limiting |= granting_teams.get(tool, set())
            for team in sorted(limiting):
                rule = snapshot.teams[team].constraints.get(tool)
                if rule:
                    sources.append(f"{snapshot.teams[team].source}#policy/tools/constraints/{tool}")
                    for arg, values in rule.items():
                        limits.setdefault(arg, set()).update(values)
        tools[tool] = ToolPermission(
            tool=tool,
            allowed_by=tuple(origins),
            constraints=(
                MappingProxyType({arg: frozenset(v) for arg, v in limits.items()})
                if limits
                else None
            ),
            constraint_sources=tuple(sources),
        )

    held_roles = frozenset(held)
    skills = _resolve_skills(snapshot, held, held_roles, team_rules)
    instructions = tuple(
        TeamInstructions(
            team,
            snapshot.teams[team].instructions_source or "",
            snapshot.teams[team].instructions or "",
        )
        for team in sorted(team_rules)
        if snapshot.teams[team].instructions
    )
    context = {
        team: MappingProxyType(dict(snapshot.teams[team].context))
        for team in sorted(team_rules)
        if snapshot.teams[team].context
    }

    data_sources = _resolve_sources(snapshot, aliases, held_roles, team_rules)
    ceilings = {
        sid: _ceiling(snapshot, held_roles, snapshot.sources[sid].owner_team)
        for sid in data_sources
    }
    max_level, max_rank = _ceiling(snapshot, held_roles, None, every_scope=True)

    return EffectivePolicy(
        config_version=snapshot.version,
        group_aliases=aliases,
        app_roles=roles_claim,
        user=user,
        teams=MappingProxyType({t: tuple(r) for t, r in team_rules.items()}),
        roles=MappingProxyType({scoped_name(*k): tuple(why) for k, why in held.items()}),
        held_roles=held_roles,
        tools=MappingProxyType(tools),
        denied=MappingProxyType({t: tuple(r) for t, r in denied.items() if t in catalog}),
        skills=MappingProxyType(skills),
        agent_instructions=instructions,
        context=MappingProxyType(context),
        data_sources=MappingProxyType(data_sources),
        max_classification=max_level,
        max_classification_rank=max_rank,
        source_classification=MappingProxyType(
            {sid: snapshot.sources[sid].classification_rank for sid in data_sources}
        ),
        source_ceilings=MappingProxyType({sid: level for sid, (level, _) in ceilings.items()}),
        source_ceiling_ranks=MappingProxyType({sid: rank for sid, (_, rank) in ceilings.items()}),
        rate_limits=MappingProxyType(_rate_limits(snapshot, team_rules)),
        data_tools=tuple(t for t in sorted(tools) if catalog[t].data_scoped),
        default_team=(
            snapshot.users.default_team.get(user)
            if user and snapshot.users.default_team.get(user) in team_rules
            else None
        ),
    )


def _rate_limits(snapshot, team_rules) -> dict[str, tuple[int, str]]:
    """Most generous limit per scope across the user's teams (like argument limits, teams only
    ever add capacity); the overall scope falls back to the platform baseline."""
    limits: dict[str, tuple[int, str]] = {}
    for team in sorted(team_rules):
        team_def = snapshot.teams[team]
        for scope, value in team_def.limits.items():
            path = "calls_per_minute" if scope == "*" else f"tools/{scope}/calls_per_minute"
            rule = f"{team_def.source}#policy/limits/{path}"
            if scope not in limits or value > limits[scope][0]:
                limits[scope] = (value, rule)
    baseline = snapshot.platform.default_calls_per_minute
    if "*" not in limits and baseline is not None:
        limits["*"] = (baseline, "platform.yaml#defaults/rate_limit")
    return limits


def _roles_in(held_roles: frozenset[tuple[Scope, str]], team: Scope) -> set[tuple[Scope, str]]:
    """Held (scope, role) pairs that count in `team`: platform roles plus that team's roles."""
    return {(s, r) for s, r in held_roles if s is PLATFORM or s == team}


def _resolve_sources(snapshot, aliases, held_roles, team_rules) -> dict[str, tuple[str, ...]]:
    member_teams, groups = set(team_rules), set(aliases)
    grants: dict[str, tuple[str, ...]] = {}
    for source in snapshot.sources.values():
        roles_here = _roles_in(held_roles, source.owner_team)
        reasons = (
            [
                f"team:{t} <- {source.source}#access/teams"
                for t in sorted(member_teams & source.access_teams)
            ]
            + [
                f"role:{scoped_name(s, r)} <- {source.source}#access/roles"
                for s, r in sorted(roles_here, key=lambda k: (k[0] or "", k[1]))
                if r in source.access_roles
            ]
            + [
                f"group:{g} <- {source.source}#access/groups"
                for g in sorted(groups & source.access_groups)
            ]
            + ([f"everyone <- {source.source}#access/everyone"] if source.access_everyone else [])
        )
        if reasons:
            grants[source.id] = tuple(reasons)
    return grants


def _ceiling(snapshot, held_roles, team: Scope, every_scope: bool = False) -> tuple[str, int]:
    """Highest classification among the roles that count in `team` (or in any scope)."""
    platform = snapshot.platform
    counted = held_roles if every_scope else _roles_in(held_roles, team)
    levels = [
        snapshot.roles[r].max_classification
        for _, r in counted
        if r in snapshot.roles and snapshot.roles[r].max_classification
    ]
    level = max(
        levels, key=platform.classification_rank, default=platform.default_max_classification
    )
    return level, platform.classification_rank(level)


def _resolve_skills(snapshot: Snapshot, held, held_roles, team_rules) -> dict[str, SkillGrant]:
    member_teams = set(team_rules)
    every_role = {r for _, r in held_roles}

    def origin(key) -> str:
        return f"role:{scoped_name(*key)} <- {held[key][0]}"

    ordered = sorted(held_roles, key=lambda k: (k[0] or "", k[1]))
    grants: dict[str, SkillGrant] = {}
    for skill in snapshot.skills.values():
        if skill.team is None:  # global skill: needs a role grant (any scope)
            reasons = [
                origin(key)
                for key in ordered
                if _role_grants_skill(snapshot.roles[key[1]].skills_allow, skill.name, skill.tags)
            ]
            roles_for_access = every_role
        else:
            if skill.team in member_teams:  # team add-on: needs membership ...
                reasons = [f"team:{skill.team} <- {team_rules[skill.team][0]}"]
            else:  # ... or a role granting every skill ("*"), e.g. admin oversight
                reasons = [
                    origin(key) for key in ordered if "*" in snapshot.roles[key[1]].skills_allow
                ]
            # its `access` roles count only when held in the skill's own team (or platform-wide)
            roles_for_access = {r for _, r in _roles_in(held_roles, skill.team)}
        if not reasons:
            continue
        if skill.access_roles or skill.access_teams:
            if not (roles_for_access & skill.access_roles or member_teams & skill.access_teams):
                continue
            reasons.append(f"access <- {skill.source}")
        grants[skill.name] = SkillGrant(skill.name, tuple(reasons), skill.team)
    return grants


def _role_grants_skill(allow: frozenset[str], name: str, tags: frozenset[str]) -> bool:
    return "*" in allow or name in allow or any(f"tag:{tag}" in allow for tag in tags)


@dataclass(frozen=True)
class SkillDecision:
    allowed: bool
    matched_rule: str  # config rule that granted or hid the skill, or "not-found"
    reason: str  # for the audit log and debugging; never shown to the caller for denials


def skill_decision(snapshot: Snapshot, policy: EffectivePolicy, name: str) -> SkillDecision:
    """Why a skill is (not) visible to a policy. Callers only ever see "unknown skill" for
    denials; the detailed reason is for the audit log."""
    grant = policy.skills.get(name)
    if grant is not None:
        return SkillDecision(True, "; ".join(grant.granted_by), "visible")
    skill = snapshot.skills.get(name)
    if skill is None:
        return SkillDecision(False, "not-found", f"no skill named '{name}' in config")
    held = {r for _, r in policy.held_roles if r in snapshot.roles}
    wildcard = any("*" in snapshot.roles[r].skills_allow for r in held)
    if skill.team is not None and skill.team not in policy.teams and not wildcard:
        return SkillDecision(
            False, skill.source, f"team add-on of '{skill.team}'; caller is not a member"
        )
    if skill.team is None and not any(
        _role_grants_skill(snapshot.roles[r].skills_allow, skill.name, skill.tags) for r in held
    ):
        via = ", ".join([f"'{name}'", *(f"'tag:{t}'" for t in sorted(skill.tags)), "'*'"])
        return SkillDecision(False, "default-deny", f"no role of the caller grants {via}")
    needs = []
    if skill.access_roles:
        where = f" in team '{skill.team}'" if skill.team is not None else ""
        needs.append(f"roles {sorted(skill.access_roles)}{where}")
    if skill.access_teams:
        needs.append(f"teams {sorted(skill.access_teams)}")
    return SkillDecision(
        False, f"{skill.source}/access", f"access requires {' or '.join(needs) or 'nothing'}"
    )


class PolicyCache:
    """EffectivePolicy per (config version, group aliases, app roles, users.yaml alias).

    Policies depend only on identities and config, so users with the same groups and no
    users.yaml entry share an entry; a direct member gets their own. A new config version
    never sees an older version's entries.
    """

    def __init__(self, max_entries: int = 1024):
        self._max = max_entries
        self._entries: dict[tuple, EffectivePolicy] = {}
        self._lock = threading.Lock()

    def get(
        self,
        snapshot: Snapshot,
        group_aliases: Iterable[str],
        app_roles: Iterable[str] = (),
        user: str | None = None,
    ) -> EffectivePolicy:
        key = (snapshot.version, frozenset(group_aliases), frozenset(app_roles), user)
        with self._lock:
            hit = self._entries.get(key)
        if hit is not None:
            return hit
        policy = resolve(snapshot, key[1], key[2], key[3])
        with self._lock:
            if len(self._entries) >= self._max or any(
                k[0] != snapshot.version for k in self._entries
            ):
                self._entries = {k: v for k, v in self._entries.items() if k[0] == snapshot.version}
                if len(self._entries) >= self._max:
                    self._entries.clear()
            self._entries[key] = policy
        return policy
