"""Personas: named sets of group aliases / app roles, for tests, `explain` and `diff`."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from sdlc_config.errors import ConfigError


@dataclass(frozen=True)
class Persona:
    name: str
    groups: tuple[str, ...]
    app_roles: tuple[str, ...] = ()


def load_personas(path: Path) -> dict[str, Persona]:
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as e:
        raise ConfigError([f"{path}: {e}"]) from e
    personas = {}
    for name, entry in (doc.get("personas") or {}).items():
        entry = entry or {}
        personas[name] = Persona(
            name=name,
            groups=tuple(entry.get("groups", [])),
            app_roles=tuple(entry.get("app_roles", [])),
        )
    if not personas:
        raise ConfigError([f"{path}: no personas defined"])
    return personas
