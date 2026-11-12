"""Entra app roles are the only source of membership besides users.yaml (CH-0011).

Before groups were removed, test_app_role_personas_match_group_personas proved that every group
persona had an app-role twin with the same access (version-03 P2 E1, last run at c645f6e). The
role values must also be defined on the sdlc-mcp app by scripts/entra_setup.ps1, or no token can
ever carry them."""

import re
from pathlib import Path

import pytest
import yaml
from sdlc_config import EffectivePolicy, load_snapshot, resolve
from sdlc_config.personas import load_personas

from tests.support.config import REPO_CONFIG, REPO_ROOT, make_config_dir
from tests.support.entra import TEST_ENV

PERSONAS = load_personas(Path(__file__).parent / "personas.yaml")


@pytest.fixture(scope="module")
def snap(tmp_path_factory):
    return load_snapshot(make_config_dir(tmp_path_factory.mktemp("cfg")), "local", TEST_ENV)


def policy(snap, name: str) -> EffectivePolicy:
    p = PERSONAS[name]
    return resolve(snap, p.app_roles, p.user)


def test_team_app_role_alone_is_enough(snap):
    """A team app role without SDLC.User still gives the team role (member inherits viewer, in
    the team's scope only: CH-0009)."""
    p = policy(snap, "team-only")
    assert set(p.teams) == {"payments"} and "viewer@payments" in p.roles
    assert "viewer" not in p.roles
    repos = p.tools["fixture_review"].constraints["repo"]
    assert set(repos) == {"payments-api", "payments-ui"}


def test_reasons_name_the_app_role_rule(snap):
    p = policy(snap, "payments-member")
    assert p.teams["payments"] == ("teams/payments.yaml#membership[0]",)  # SDLC.Payments.Member
    assert "roles.yaml#bindings[1]" in p.roles["viewer"]  # SDLC.User


def test_unknown_app_role_grants_only_signed_in(snap):
    p = policy(snap, "unknown-app-role")
    assert set(p.roles) == {"signed-in"} and not p.teams


def _config_app_roles() -> set[str]:
    found: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("app_role"), str):
                found.add(node["app_role"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for path in REPO_CONFIG.rglob("*.yaml"):
        walk(yaml.safe_load(path.read_text(encoding="utf-8")))
    return found


def _script_app_roles() -> set[str]:
    script = (REPO_ROOT / "scripts" / "entra_setup.ps1").read_text(encoding="utf-8")
    block = re.search(r"\$AppRoles = \[ordered\]@\{(.*?)\n\}", script, re.S)
    assert block, "entra_setup.ps1 must define $AppRoles"
    return set(re.findall(r"'(SDLC\.[A-Za-z.]+)'\s*=", block.group(1)))


def test_config_app_roles_are_defined_by_the_setup_script():
    in_config, in_script = _config_app_roles(), _script_app_roles()
    assert in_config, "config grants nothing by app role"
    assert in_config == in_script, (in_config - in_script, in_script - in_config)
