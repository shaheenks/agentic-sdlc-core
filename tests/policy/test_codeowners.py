"""CODEOWNERS covers every team, team skill folder, source and security-critical path with a rule
of its own (governance: team files are reviewed by that team's owners, the access model by
platform-admins). Adding a team or source without a CODEOWNERS rule fails here."""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CRITICAL = [
    "/config/platform.yaml",
    "/config/roles.yaml",
    "/config/tools.yaml",
    "/config/skills.yaml",
    "/config/schemas/",
    "/config/env/",
    "/libs/sdlc_auth/",
    "/libs/sdlc_policy/",
    "/libs/sdlc_config/",
    "/libs/sdlc_db/",
    "/db/",
    "/infra/",
    "/.github/",
]


def rules() -> dict[str, list[str]]:
    out = {}
    for line in (REPO / ".github/CODEOWNERS").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            pattern, *owners = line.split()
            out[pattern] = owners
    return out


def test_every_rule_has_an_owner():
    assert all(owners and all(o.startswith("@") for o in owners) for owners in rules().values())


@pytest.mark.parametrize("path", CRITICAL)
def test_security_critical_paths_have_rules(path):
    assert path in rules()


def test_every_team_and_source_has_a_rule():
    have = rules()
    missing = [f"/config/teams/{p.name}" for p in (REPO / "config/teams").glob("*.yaml")] + [
        f"/config/sources/{p.name}" for p in (REPO / "config/sources").glob("*.yaml")
    ]
    missing += [f"/skills/teams/{p.name}/" for p in (REPO / "skills/teams").iterdir() if p.is_dir()]
    assert [p for p in missing if p not in have] == []
