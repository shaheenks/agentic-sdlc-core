"""The uv workspace lists every component and wires them as packages (NFR-MAINT-001, CH-0006)."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AREAS = ("libs", "ingest", "mcp_servers", "agents")


def load(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def component_dirs() -> set[str]:
    return {
        p.parent.relative_to(ROOT).as_posix()
        for area in AREAS
        for p in (ROOT / area).glob("*/pyproject.toml")
    }


def test_every_component_is_a_member():
    members = set(load(ROOT / "pyproject.toml")["tool"]["uv"]["workspace"]["members"])
    assert component_dirs() == members


def test_every_member_has_a_workspace_source():
    sources = load(ROOT / "pyproject.toml")["tool"]["uv"]["sources"]
    for member in component_dirs():
        name = load(ROOT / member / "pyproject.toml")["project"]["name"]
        assert sources.get(name) == {"workspace": True}, member


# A member reaching into another's source tree instead of importing its package.
PATH_HACK = re.compile(
    r"sys\.path\.(insert|append)|^\s*(from|import)\s+(libs|ingest|mcp_servers|agents)\b", re.M
)


def test_no_member_imports_another_by_path():
    offenders = [
        p.relative_to(ROOT).as_posix()
        for member in component_dirs()
        for p in (ROOT / member).rglob("*.py")
        if ".venv" not in p.parts and PATH_HACK.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []
