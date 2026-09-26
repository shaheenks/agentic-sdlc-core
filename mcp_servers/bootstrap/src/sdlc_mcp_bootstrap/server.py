"""Bootstrap MCP server.

Stage 1 (walking skeleton): ping, list_skills, load_skill over streamable HTTP, no auth.
Stage 2 adds Entra JWT validation and ConfigStore; Stage 3 adds RBAC filtering. Until then
this server must only run locally.
"""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from starlette.requests import Request
from starlette.responses import JSONResponse

DEFAULT_SKILLS_DIR = Path(__file__).resolve().parents[4] / "skills" / "bootstrap"


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    instructions: str


def parse_skill(path: Path) -> Skill:
    """Parse a SKILL.md file: YAML frontmatter (name, description) + markdown body."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path}: missing YAML frontmatter")
    _, frontmatter, body = text.split("---", 2)
    meta = yaml.safe_load(frontmatter) or {}
    for key in ("name", "description"):
        if not meta.get(key):
            raise ValueError(f"{path}: frontmatter is missing '{key}'")
    return Skill(name=meta["name"], description=meta["description"], instructions=body.strip())


def discover_skills(skills_dir: Path) -> dict[str, Skill]:
    """Load every <skills_dir>/<skill>/SKILL.md, keyed by skill name."""
    skills: dict[str, Skill] = {}
    for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
        skill = parse_skill(skill_file)
        if skill.name in skills:
            raise ValueError(f"duplicate skill name '{skill.name}' in {skills_dir}")
        skills[skill.name] = skill
    return skills


def build_server(skills_dir: Path) -> FastMCP:
    # Skills are loaded once at startup so a malformed SKILL.md fails fast.
    skills = discover_skills(skills_dir)
    mcp = FastMCP(
        name="sdlc-mcp-bootstrap",
        instructions="Central SDLC tool server. Use list_skills, then load_skill before a task.",
    )

    @mcp.tool
    def ping() -> str:
        """Liveness check. Returns 'pong'."""
        return "pong"

    @mcp.tool
    def list_skills() -> list[dict[str, str]]:
        """List available SDLC skills (name + description). Load one with load_skill."""
        return [{"name": s.name, "description": s.description} for s in skills.values()]

    @mcp.tool
    def load_skill(name: str) -> dict[str, str]:
        """Return the full instructions of a skill returned by list_skills."""
        skill = skills.get(name)
        if skill is None:
            raise ToolError(f"unknown skill '{name}'")
        return {
            "name": skill.name,
            "description": skill.description,
            "instructions": skill.instructions,
        }

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "skills": len(skills)})

    return mcp


def main() -> None:
    skills_dir = Path(os.environ.get("SDLC_SKILLS_DIR", DEFAULT_SKILLS_DIR))
    server = build_server(skills_dir)
    server.run(
        transport="http",
        host=os.environ.get("MCP_HOST", "127.0.0.1"),
        port=int(os.environ.get("MCP_PORT", "8080")),
    )


if __name__ == "__main__":
    main()
