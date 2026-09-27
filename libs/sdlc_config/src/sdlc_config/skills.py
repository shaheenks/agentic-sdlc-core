"""Skill packages: SKILL.md parsing and safe path resolution (Stage 4).

Naming strategy (skills/README.md): lowercase kebab-case, globally unique, folder name = SKILL.md
`name` = config key. Paths in config are relative to the repo root and must stay in `skills/`.
"""

from pathlib import Path

import yaml


class SkillFileError(ValueError):
    pass


def parse_skill_md(text: str, where: str) -> tuple[str, str, str]:
    """(name, description, instructions) from a SKILL.md: YAML frontmatter + markdown body."""
    if not text.startswith("---"):
        raise SkillFileError(f"{where}: missing YAML frontmatter")
    try:
        _, frontmatter, body = text.split("---", 2)
        meta = yaml.safe_load(frontmatter) or {}
    except (ValueError, yaml.YAMLError) as e:
        raise SkillFileError(f"{where}: invalid frontmatter: {e}") from e
    for key in ("name", "description"):
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            raise SkillFileError(f"{where}: frontmatter is missing '{key}'")
    return meta["name"].strip(), meta["description"].strip(), body.strip()


def resolve_in_skills(repo_root: Path, rel: str) -> Path:
    """Resolve a config path (e.g. skills/core/x) and refuse anything outside <repo>/skills."""
    skills_root = (repo_root / "skills").resolve()
    path = (repo_root / rel).resolve()
    if path != skills_root and skills_root not in path.parents:
        raise SkillFileError(f"{rel}: path must stay inside skills/")
    return path
