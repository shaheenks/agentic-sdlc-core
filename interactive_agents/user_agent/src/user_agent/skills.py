"""The skills in `skills/` (Skill Library), read with ADK's own loader. Locally they come from the repository; the
deployment copies them into the package (`user_agent/skills`). `SDLC_SKILLS_DIR` overrides both."""

import os
from functools import cache
from pathlib import Path

HERE = Path(__file__).resolve()
PACKAGED = HERE.parent / "skills"
# In the repository: interactive_agents/user_agent/src/user_agent/skills.py -> <root>/skills. Deployed, the package
# sits near the filesystem root, so there is no such parent.
REPOSITORY = HERE.parents[4] / "skills" if len(HERE.parents) > 4 else None


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
