"""The repo config itself (not the test fixture): teams, their members and the team sources.

tests/support/config.py adds fixture-only group membership and a local source to sdlc-platform;
these tests read config/ directly so the real setup stays pinned."""

from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parents[2] / "config"


def doc(rel: str) -> dict:
    return yaml.safe_load((CONFIG / rel).read_text(encoding="utf-8"))


def test_teams():
    assert {p.stem for p in (CONFIG / "teams").glob("*.yaml")} == {"payments", "sdlc-platform"}


def test_sdlc_platform_members_come_only_from_users_yaml():
    team = doc("teams/sdlc-platform.yaml")
    assert team["membership"] == []  # no Entra group per role: env/<env>/users.yaml
    assert team["addons"]["skills"] == {
        "infra-change-review": {"path": "skills/teams/sdlc-platform/infra-change-review"}
    }
    repos = {t: c["args"]["repo"]["in"] for t, c in team["policy"]["tools"]["constraints"].items()}
    assert repos == {"review_code": ["agentic-sdlc-core"], "generate_tests": ["agentic-sdlc-core"]}


def test_sdlc_platform_sources():
    owned = {
        p.stem
        for p in (CONFIG / "sources").glob("*.yaml")
        if doc(f"sources/{p.name}")["metadata"]["owner_team"] == "sdlc-platform"
    }
    assert owned == {"sdlc-platform", "eng-standards"}
    source = doc("sources/sdlc-platform.yaml")
    assert source["spec"]["location"] == "https://github.com/shaheenks/agentic-sdlc-core.git"
    assert source["spec"]["ref"] == "main" and "credentials" not in source["spec"]
    assert "github.com" in doc("platform.yaml")["knowledge"]["allowed_hosts"]
