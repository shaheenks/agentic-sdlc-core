"""Personas: named sets of Entra app roles and/or a users.yaml user, for tests, `explain` and
`diff`. Entra groups are not used (CH-0011)."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from sdlc_config.errors import ConfigError


@dataclass(frozen=True)
class Persona:
    name: str
    app_roles: tuple[str, ...] = ()
    user: str | None = None  # users.yaml alias (direct member)


def load_personas(path: Path) -> dict[str, Persona]:
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as e:
        raise ConfigError([f"{path}: {e}"]) from e
    personas, problems = {}, []
    for name, entry in (doc.get("personas") or {}).items():
        entry = entry or {}
        if "groups" in entry:
            problems.append(f"{path}: personas/{name}/groups: Entra groups are no longer used")
        personas[name] = Persona(
            name=name,
            app_roles=tuple(entry.get("app_roles", [])),
            user=entry.get("user"),
        )
    if problems:
        raise ConfigError(problems)
    if not personas:
        raise ConfigError([f"{path}: no personas defined"])
    return personas
