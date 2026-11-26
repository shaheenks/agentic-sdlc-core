"""The skills in `skills/` (Skill Library), read with ADK's own loader (sdlc_adk). Locally they come from the
repository; the deployment copies them into the package (`user_agent/skills`). `SDLC_SKILLS_DIR` overrides both."""

import os
from pathlib import Path

from sdlc_adk import load_skills, skills_dir

HERE = Path(__file__).resolve()
PACKAGED = HERE.parent / "skills"
# In the repository: interactive_agents/user_agent/src/user_agent/skills.py -> <root>/skills. Deployed, the package
# sits near the filesystem root, so there is no such parent.
REPOSITORY = HERE.parents[4] / "skills" if len(HERE.parents) > 4 else None


def skill(name: str) -> str:
    """A skill's instructions (its Markdown body)."""
    return load_skills(skills_dir((os.environ.get("SDLC_SKILLS_DIR"), PACKAGED, REPOSITORY)))[name]
