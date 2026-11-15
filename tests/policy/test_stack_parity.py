"""One catalog, two stacks (CH-0021, design N13): every persona resolves to the same access from
its Google groups (GCP stack) as from its Entra app roles (Entra stack)."""

from pathlib import Path

import pytest
from sdlc_config import load_snapshot, resolve
from sdlc_config.personas import (
    ENTRA,
    GOOGLE,
    load_personas,
    parity_problems,
    resolve_persona,
)

from tests.support.config import group_for, make_config_dir
from tests.support.entra import TEST_ENV

PERSONAS = load_personas(Path(__file__).parent / "personas.yaml")


@pytest.fixture(scope="module")
def snap(tmp_path_factory):
    return load_snapshot(make_config_dir(tmp_path_factory.mktemp("cfg")), "local", TEST_ENV)


def test_every_persona_resolves_the_same_on_both_stacks(snap):
    assert parity_problems(snap, PERSONAS) == []


@pytest.mark.parametrize("name", [n for n, p in PERSONAS.items() if p.parity])
def test_roles_and_tools_match_per_persona(snap, name):
    entra = resolve_persona(snap, PERSONAS[name], ENTRA)
    google = resolve_persona(snap, PERSONAS[name], GOOGLE)
    assert set(google.roles) == set(entra.roles)
    assert set(google.tools) == set(entra.tools)
    assert google.readable_sources == entra.readable_sources


def test_a_missing_group_fails_parity(snap):
    """Drop one group from a persona: the check names the persona and the differing grants."""
    broken = {
        "payments-member": PERSONAS["payments-member"].__class__(
            name="payments-member",
            app_roles=PERSONAS["payments-member"].app_roles,
            groups=(group_for("SDLC.User"),),
        )
    }
    problems = parity_problems(snap, broken)
    assert len(problems) == 1 and "payments-member" in problems[0] and "roles" in problems[0]


def test_groups_never_grant_on_the_entra_stack_and_app_roles_never_on_gcp(snap):
    """Each stack reads only its own membership: an Entra persona's policy ignores groups."""
    persona = PERSONAS["admin"]
    assert "admin" not in resolve(snap, (), None, ()).roles
    assert "admin" in resolve(snap, persona.app_roles).roles
    assert "admin" in resolve(snap, (), None, persona.groups).roles
    entra_only = resolve_persona(snap, persona.__class__("x", app_roles=()), GOOGLE)
    assert "admin" not in entra_only.roles


def test_group_reasons_name_the_binding_rule(snap):
    google = resolve_persona(snap, PERSONAS["payments-member"], GOOGLE)
    assert google.teams["payments"] == ("teams/payments.yaml#membership[0]",)
    assert google.groups == (group_for("SDLC.Payments.Member"), group_for("SDLC.User"))
    assert "groups" in google.explain()


def test_group_emails_are_case_insensitive(snap):
    assert "admin" in resolve(snap, (), None, [group_for("SDLC.Admin").upper()]).roles


def test_parity_is_skipped_while_no_group_is_bound(tmp_path):
    """An environment without the GCP stack configured has nothing to compare."""
    config_dir = make_config_dir(tmp_path)
    for path in [config_dir / "roles.yaml", *(config_dir / "teams").glob("*.yaml")]:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        path.write_text("".join(x for x in lines if "group: " not in x), encoding="utf-8")
    bare = load_snapshot(config_dir, "local", TEST_ENV)
    assert bare.group_values == frozenset() and parity_problems(bare, PERSONAS) == []
