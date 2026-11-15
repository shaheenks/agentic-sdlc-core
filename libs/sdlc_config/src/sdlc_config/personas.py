"""Personas: named callers for tests, `explain`, `diff` and the stack parity check.

A persona is how one kind of user looks on each stack (CH-0021, design N13):
  - Entra stack: a set of Entra app roles (`app_roles`), users.yaml matched on oid;
  - GCP stack: a set of Google group emails (`groups`), users.yaml matched on email;
plus an optional users.yaml `user`. Entra groups are not used (CH-0011).

The parity check resolves each persona that names both forms once per stack and fails when the
two differ, so the one config catalog grants the same on both stacks.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from sdlc_config.errors import ConfigError
from sdlc_config.model import Snapshot
from sdlc_config.resolver import EffectivePolicy, resolve

ENTRA, GOOGLE = "entra", "google"
STACKS = (ENTRA, GOOGLE)


@dataclass(frozen=True)
class Persona:
    name: str
    app_roles: tuple[str, ...] = ()
    user: str | None = None  # users.yaml alias (direct member)
    groups: tuple[str, ...] = ()  # Google group emails (GCP stack)
    stacks: tuple[str, ...] = STACKS  # the stacks this persona exists on

    @property
    def parity(self) -> bool:
        """Checked for parity: it exists on both stacks."""
        return set(self.stacks) == set(STACKS)


def load_personas(path: Path) -> dict[str, Persona]:
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as e:
        raise ConfigError([f"{path}: {e}"]) from e
    personas, problems = {}, []
    for name, entry in (doc.get("personas") or {}).items():
        entry = entry or {}
        stacks = tuple(entry.get("stacks", STACKS))
        if not stacks or set(stacks) - set(STACKS):
            problems.append(f"{path}: personas/{name}/stacks: must be some of {list(STACKS)}")
        groups = entry.get("groups", [])
        if any("@" not in str(g) for g in groups):
            problems.append(
                f"{path}: personas/{name}/groups: Google group emails only (Entra groups are "
                "no longer used, CH-0011)"
            )
        personas[name] = Persona(
            name=name,
            app_roles=tuple(entry.get("app_roles", [])),
            user=entry.get("user"),
            groups=tuple(str(g).lower() for g in groups),
            stacks=stacks,
        )
    if problems:
        raise ConfigError(problems)
    if not personas:
        raise ConfigError([f"{path}: no personas defined"])
    return personas


def persona_user(snapshot: Snapshot, persona: Persona, stack: str = ENTRA) -> str | None:
    """The persona's users.yaml alias as `stack` would match it: the Entra stack only matches an
    entry with an oid (pending entries match nothing), the GCP stack any entry by its email."""
    if not persona.user or persona.user not in snapshot.users.email_by_alias:
        return None  # users.yaml is per environment
    if stack == ENTRA and persona.user in snapshot.users.pending:
        return None
    return persona.user


def resolve_persona(snapshot: Snapshot, persona: Persona, stack: str = ENTRA) -> EffectivePolicy:
    """The persona's policy on one stack: app roles on Entra, groups on the GCP stack."""
    user = persona_user(snapshot, persona, stack)
    if stack == GOOGLE:
        return resolve(snapshot, (), user, persona.groups)
    return resolve(snapshot, persona.app_roles, user)


def _grants(policy: EffectivePolicy) -> dict:
    """What a persona can do, without the reasons (those name different rules per stack)."""
    return {
        "teams": sorted(policy.teams),
        "roles": sorted(policy.roles),
        "tools": {
            t: {a: sorted(v) for a, v in (p.constraints or {}).items()}
            for t, p in sorted(policy.tools.items())
        },
        "skills": sorted(policy.skills),
        "sources": policy.readable_sources,
        "ceilings": dict(sorted(policy.source_ceilings.items())),
        "rate_limits": {s: limit for s, (limit, _) in sorted(policy.rate_limits.items())},
    }


def parity_problems(snapshot: Snapshot, personas: dict[str, Persona]) -> list[str]:
    """Personas on both stacks that resolve differently from their groups than from their app
    roles. Skipped (no problem) while config binds no Google group at all: the GCP stack is not
    configured in this environment yet."""
    if not snapshot.group_values:
        return []
    problems = []
    for persona in personas.values():
        if not persona.parity:
            continue
        entra = _grants(resolve_persona(snapshot, persona, ENTRA))
        google = _grants(resolve_persona(snapshot, persona, GOOGLE))
        diff = sorted(k for k in entra if entra[k] != google[k])
        if diff:
            problems.append(
                f"persona {persona.name}: resolves differently on the GCP stack ({', '.join(diff)}"
                f"): entra roles {entra['roles']}, google roles {google['roles']}"
            )
    return problems
