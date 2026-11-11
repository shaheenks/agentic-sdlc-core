"""version-03 P2 E1: Entra app roles grant exactly what the matching groups grant.

Each app-role persona (tests/policy/personas.yaml) must resolve to the same permissions as its
group twin: teams, roles, tools + argument limits, skills, readable data, rate limits and team
context. Only the "why" (matched rule names) may differ. The role values must also be defined
on the sdlc-mcp app by scripts/entra_setup.ps1, or no token can ever carry them."""

import re
from pathlib import Path

import pytest
import yaml
from sdlc_config import EffectivePolicy, load_snapshot, resolve
from sdlc_config.personas import load_personas

from tests.support.config import REPO_CONFIG, REPO_ROOT, make_config_dir
from tests.support.entra import TEST_ENV

PERSONAS = load_personas(Path(__file__).parent / "personas.yaml")

TWINS = {
    "approle-viewer": "viewer",
    "approle-payments-dev": "payments-dev",
    "approle-payments-lead": "payments-lead",
    "approle-platform-dev": "platform-dev",
    "approle-admin": "admin",
    "mixed-dev": "multi-team-dev",
    "unknown-app-role": "nobody",
}


@pytest.fixture(scope="module")
def snap(tmp_path_factory):
    return load_snapshot(make_config_dir(tmp_path_factory.mktemp("cfg")), "local", TEST_ENV)


def policy(snap, name: str) -> EffectivePolicy:
    p = PERSONAS[name]
    return resolve(snap, p.groups, p.app_roles, p.user)


def granted(p: EffectivePolicy) -> dict:
    """What a policy grants, without the rule names that explain it."""
    return {
        "teams": sorted(p.teams),
        "roles": sorted(p.roles),
        "tools": {
            name: {arg: sorted(v) for arg, v in t.constraints.items()} if t.constraints else None
            for name, t in p.tools.items()
        },
        "denied": sorted(p.denied),
        "skills": {name: g.team for name, g in p.skills.items()},
        "readable": p.readable_sources,
        "max_classification": p.max_classification,
        "data_tools": sorted(p.data_tools),
        "rate_limits": {scope: limit for scope, (limit, _) in p.rate_limits.items()},
        "instructions": [i.team for i in p.agent_instructions],
        "context": {t: dict(c) for t, c in p.context.items()},
    }


@pytest.mark.parametrize("approle,group", TWINS.items())
def test_app_role_personas_match_group_personas(snap, approle, group):
    assert PERSONAS[approle].app_roles, approle
    assert granted(policy(snap, approle)) == granted(policy(snap, group))


def test_team_app_role_alone_is_enough(snap):
    """A team app role without SDLC.User still gives the team role (developer inherits viewer)."""
    p = policy(snap, "approle-team-only")
    assert set(p.teams) == {"payments"} and "viewer" in p.roles
    repos = p.tools["fixture_review"].constraints["repo"]
    assert set(repos) == {"payments-api", "payments-ui"}


def test_reasons_name_the_app_role_rule(snap):
    p = policy(snap, "approle-payments-dev")
    assert p.teams["payments"] == ("teams/payments.yaml#membership[2]",)  # SDLC.Payments.Developer
    assert "roles.yaml#bindings[2]" in p.roles["viewer"]  # SDLC.User


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
