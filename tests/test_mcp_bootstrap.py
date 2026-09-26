from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from sdlc_mcp_bootstrap.server import build_server, discover_skills, parse_skill

REPO_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_SKILLS = REPO_ROOT / "skills" / "bootstrap"


@pytest.fixture
def server():
    return build_server(BOOTSTRAP_SKILLS)


async def test_ping(server):
    async with Client(server) as client:
        result = await client.call_tool("ping", {})
        assert result.data == "pong"


async def test_list_tools_exposes_stage1_tools(server):
    async with Client(server) as client:
        names = {t.name for t in await client.list_tools()}
        assert names == {"ping", "list_skills", "load_skill"}


async def test_list_and_load_skill(server):
    async with Client(server) as client:
        listed = (await client.call_tool("list_skills", {})).data
        assert {"write-user-story"} <= {s["name"] for s in listed}
        loaded = (await client.call_tool("load_skill", {"name": "write-user-story"})).data
        assert "Given" in loaded["instructions"]


@pytest.mark.parametrize("name", ["nope", "../agents", "write-user-story/../../CLAUDE"])
async def test_load_unknown_skill_is_rejected(server, name):
    async with Client(server) as client:
        with pytest.raises(ToolError):
            await client.call_tool("load_skill", {"name": name})


def test_skill_without_frontmatter_fails(tmp_path):
    bad = tmp_path / "bad" / "SKILL.md"
    bad.parent.mkdir()
    bad.write_text("# no frontmatter", encoding="utf-8")
    with pytest.raises(ValueError, match="frontmatter"):
        parse_skill(bad)


def test_duplicate_skill_names_fail(tmp_path):
    for folder in ("a", "b"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "SKILL.md").write_text(
            "---\nname: dup\ndescription: d\n---\nbody", encoding="utf-8"
        )
    with pytest.raises(ValueError, match="duplicate"):
        discover_skills(tmp_path)
