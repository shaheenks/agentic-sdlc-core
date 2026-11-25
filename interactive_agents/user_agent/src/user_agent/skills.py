"""The skills in `skills/` (Skill Library), read with ADK's own loader. Locally they come from the repository; the
deployment copies them into the package (`user_agent/skills`). `SDLC_SKILLS_DIR` overrides both."""

import os
from functools import cache
from pathlib import Path

PACKAGED = Path(__file__).resolve().parent / "skills"
REPOSITORY = Path(__file__).resolve().parents[4] / "skills"


def skills_dir() -> Path:
    for candidate in (os.environ.get("SDLC_SKILLS_DIR"), PACKAGED, REPOSITORY):
        if candidate and Path(candidate).is_dir():
            return Path(candidate)
    raise FileNotFoundError("no skills directory: set SDLC_SKILLS_DIR")


@cache
def _all() -> dict[str, str]:
    from google.adk.skills import load_skills_from_dir

    return {s.frontmatter.name: s.instructions for s in load_skills_from_dir(skills_dir())}


def skill(name: str) -> str:
    """A skill's instructions (its Markdown body)."""
    return _all()[name]
