"""Resolve a principal's identities into an EffectivePolicy (plan: resolution steps 1-5).

identities (group aliases + Entra app roles)
  -> teams (membership) + global bindings -> roles, expanded through `inherits`
  -> allowed tools (role allows, "*" = whole catalog) minus denies (role + team); deny wins
  -> argument limits: unioned across the member teams that constrain a tool;
     tools granted by an `unconstrained` role get none.
  -> skills (step 6): global skills granted by role (name, "tag:<tag>", "*") and, when the skill
     sets `access`, held by one of its roles or teams; plus member teams' add-on skills (with
     their `access` roles). A "*" skill grant (admin) also covers every team's add-ons.
  -> agent context (step 8): member teams' instructions (AGENT_ADDENDUM) and context.
  -> data (step 7): allowed sources = sources whose `access` matches the caller's teams, roles
     or group aliases (the ONLY grant for data); max classification = highest level across the
     caller's roles (platform default otherwise). Postgres RLS enforces both on every query.
Every role, grant, deny and limit records the config rule it came from.
"""

import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from sdlc_config.model import IdentityRef, Snapshot


@dataclass(frozen=True)
class ToolPermission:
    tool: str
    allowed_by: tuple[str, ...]  # e.g. "role:developer <- teams/payments.yaml#membership[0]"
    # arg -> allowed values; None = no limits
    constraints: Mapping[str, frozenset[str]] | None = None
    constraint_sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkillGrant:
    skill: str
    granted_by: tuple[str, ...]  # e.g. "role:developer <- ..." or "team:payments <- ..."
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
    roles: Mapping[str, tuple[str, ...]]  # role -> reasons (binding/membership rule or inherits)
    tools: Mapping[str, ToolPermission]  # allowed tools only
    denied: Mapping[str, tuple[str, ...]] = field(default_factory=dict)  # tool -> deny rules
    skills: Mapping[str, SkillGrant] = field(default_factory=dict)  # visible skills only
    agent_instructions: tuple[TeamInstructions, ...] = ()
    context: Mapping[str, Mapping[str, str]] = field(default_factory=dict)  # team -> values
    data_sources: Mapping[str, tuple[str, ...]] = field(default_factory=dict)  # id -> grant rules
    max_classification: str = "public"
    max_classification_rank: int = 0
    # Current classification rank of each granted source (from this config version).
    source_classification: Mapping[str, int] = field(default_factory=dict)

    @property
    def readable_sources(self) -> tuple[str, ...]:
        """Granted sources at or below the caller's ceiling, by the CURRENT config. This is what the
        RLS context carries, so raising a source's classification takes effect on the next request
        without re-ingesting (rows keep their own stamp as a second check; a lowered
        classification applies once ingest re-stamps the rows: fail closed). A source without a
        known classification is not readable."""
        return tuple(
            sid
            for sid in sorted(self.data_sources)
            if self.source_classification.get(sid, 1 << 30) <= self.max_classification_rank
        )

    def allows(self, tool: str) -> bool:
        return tool in self.tools

    def sees_skill(self, name: str) -> bool:
        return name in self.skills

    def explain(self) -> dict:
        """JSON-friendly view for whoami(explain) / config_explain / CLI."""
        return {
            "config_version": self.config_version,
            "group_aliases": list(self.group_aliases),
            "app_roles": list(self.app_roles),
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
            "data": {
                "sources": {sid: list(r) for sid, r in sorted(self.data_sources.items())},
                "max_classification": self.max_classification,
                "readable": list(self.readable_sources),
            },
            "agent_context": {
                "instructions": [
                    {"team": i.team, "source": i.source} for i in self.agent_instructions
                ],
                "context": {t: dict(c) for t, c in sorted(self.context.items())},
            },
        }


def resolve(
    snapshot: Snapshot, group_aliases: Iterable[str], app_roles: Iterable[str] = ()
) -> EffectivePolicy:
    aliases, roles_claim = tuple(sorted(set(group_aliases))), tuple(sorted(set(app_roles)))
    # Every resolved principal is a signed-in user, so `everyone` bindings always apply.
    ids = {IdentityRef("everyone", "*")}
    ids |= {IdentityRef("group", a) for a in aliases}
    ids |= {IdentityRef("app_role", r) for r in roles_claim}

    # 1-3: teams and directly granted roles
    team_rules: dict[str, list[str]] = {}
    role_reasons: dict[str, list[str]] = {}
    for binding in snapshot.bindings:
        if binding.ref in ids:
            for role in binding.roles:
                role_reasons.setdefault(role, []).append(binding.rule)
    for team in snapshot.teams.values():
        for member in team.membership:
            if member.ref in ids:
                team_rules.setdefault(team.name, []).append(member.rule)
                for role in member.roles:
                    role_reasons.setdefault(role, []).append(member.rule)

    # 4: expand inherits (the loader rejects cycles; `seen` guards anyway)
    pending, seen = list(role_reasons), set()
    while pending:
        role = pending.pop()
        if role in seen:
            continue
        seen.add(role)
        for parent in snapshot.roles[role].inherits:
            reason = f"inherited from role:{role}"
            if reason not in role_reasons.setdefault(parent, []):
                role_reasons[parent].append(reason)
            pending.append(parent)

    # 5: allowed tools, denies, argument limits
    catalog = snapshot.tools
    allowed_by: dict[str, list[str]] = {}
    unconstrained: set[str] = set()
    denied: dict[str, list[str]] = {}
    for role in sorted(role_reasons):
        definition = snapshot.roles[role]
        origin = f"role:{role} <- {role_reasons[role][0]}"
        granted = catalog.keys() if "*" in definition.tools_allow else definition.tools_allow
        for tool in granted:
            allowed_by.setdefault(tool, []).append(origin)
            if definition.unconstrained:
                unconstrained.add(tool)
        for tool in definition.tools_deny:
            denied.setdefault(tool, []).append(f"role:{role} deny")
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
            for team in sorted(team_rules):
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

    skills = _resolve_skills(snapshot, role_reasons, team_rules)
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

    data_sources = _resolve_sources(snapshot, aliases, role_reasons, team_rules)
    max_level, max_rank = _max_classification(snapshot, role_reasons)

    return EffectivePolicy(
        config_version=snapshot.version,
        group_aliases=aliases,
        app_roles=roles_claim,
        teams=MappingProxyType({t: tuple(r) for t, r in team_rules.items()}),
        roles=MappingProxyType({r: tuple(why) for r, why in role_reasons.items()}),
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
    )


def _resolve_sources(snapshot, aliases, role_reasons, team_rules) -> dict[str, tuple[str, ...]]:
    held_roles, member_teams, groups = set(role_reasons), set(team_rules), set(aliases)
    grants: dict[str, tuple[str, ...]] = {}
    for source in snapshot.sources.values():
        reasons = (
            [
                f"team:{t} <- {source.source}#access/teams"
                for t in sorted(member_teams & source.access_teams)
            ]
            + [
                f"role:{r} <- {source.source}#access/roles"
                for r in sorted(held_roles & source.access_roles)
            ]
            + [
                f"group:{g} <- {source.source}#access/groups"
                for g in sorted(groups & source.access_groups)
            ]
        )
        if reasons:
            grants[source.id] = tuple(reasons)
    return grants


def _max_classification(snapshot, role_reasons) -> tuple[str, int]:
    platform = snapshot.platform
    levels = [
        snapshot.roles[r].max_classification
        for r in role_reasons
        if r in snapshot.roles and snapshot.roles[r].max_classification
    ]
    level = max(
        levels, key=platform.classification_rank, default=platform.default_max_classification
    )
    return level, platform.classification_rank(level)


def _resolve_skills(snapshot: Snapshot, role_reasons, team_rules) -> dict[str, SkillGrant]:
    held_roles, member_teams = set(role_reasons), set(team_rules)
    grants: dict[str, SkillGrant] = {}
    for skill in snapshot.skills.values():
        if skill.team is None:  # global skill: needs a role grant
            reasons = [
                f"role:{role} <- {role_reasons[role][0]}"
                for role in sorted(held_roles)
                if _role_grants_skill(snapshot.roles[role].skills_allow, skill.name, skill.tags)
            ]
        elif skill.team in member_teams:  # team add-on: needs membership ...
            reasons = [f"team:{skill.team} <- {team_rules[skill.team][0]}"]
        else:  # ... or a role granting every skill ("*"), e.g. admin oversight
            reasons = [
                f"role:{role} <- {role_reasons[role][0]}"
                for role in sorted(held_roles)
                if "*" in snapshot.roles[role].skills_allow
            ]
        if not reasons:
            continue
        if skill.access_roles or skill.access_teams:
            if not (held_roles & skill.access_roles or member_teams & skill.access_teams):
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
    held = set(policy.roles)
    wildcard = any("*" in snapshot.roles[r].skills_allow for r in held if r in snapshot.roles)
    if skill.team is not None and skill.team not in policy.teams and not wildcard:
        return SkillDecision(
            False, skill.source, f"team add-on of '{skill.team}'; caller is not a member"
        )
    if skill.team is None and not any(
        _role_grants_skill(snapshot.roles[r].skills_allow, skill.name, skill.tags)
        for r in held
        if r in snapshot.roles
    ):
        via = ", ".join([f"'{name}'", *(f"'tag:{t}'" for t in sorted(skill.tags)), "'*'"])
        return SkillDecision(False, "default-deny", f"no role of the caller grants {via}")
    needs = []
    if skill.access_roles:
        needs.append(f"roles {sorted(skill.access_roles)}")
    if skill.access_teams:
        needs.append(f"teams {sorted(skill.access_teams)}")
    return SkillDecision(
        False, f"{skill.source}/access", f"access requires {' or '.join(needs) or 'nothing'}"
    )


class PolicyCache:
    """EffectivePolicy per (config version, group aliases, app roles).

    Policies depend only on identities and config, not on the user, so users with the same
    groups share an entry. A new config version never sees an older version's entries.
    """

    def __init__(self, max_entries: int = 1024):
        self._max = max_entries
        self._entries: dict[tuple, EffectivePolicy] = {}
        self._lock = threading.Lock()

    def get(
        self, snapshot: Snapshot, group_aliases: Iterable[str], app_roles: Iterable[str] = ()
    ) -> EffectivePolicy:
        key = (snapshot.version, frozenset(group_aliases), frozenset(app_roles))
        with self._lock:
            hit = self._entries.get(key)
        if hit is not None:
            return hit
        policy = resolve(snapshot, key[1], key[2])
        with self._lock:
            if len(self._entries) >= self._max or any(
                k[0] != snapshot.version for k in self._entries
            ):
                self._entries = {k: v for k, v in self._entries.items() if k[0] == snapshot.version}
                if len(self._entries) >= self._max:
                    self._entries.clear()
            self._entries[key] = policy
        return policy
