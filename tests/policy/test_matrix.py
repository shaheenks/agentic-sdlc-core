"""Stage 3f: persona matrix (tests/policy/matrix.yaml) against the repo config.

Every row runs once per stack the persona exists on (CH-0021): from its Entra app roles and from
its Google groups, so both stacks are held to the same expectations."""

from pathlib import Path

import pytest
import yaml
from sdlc_config import load_snapshot
from sdlc_config.personas import load_personas, resolve_persona
from sdlc_policy import authorize

from tests.support.config import GOOGLE_DOMAIN, make_config_dir
from tests.support.entra import TEST_ENV

HERE = Path(__file__).parent
PERSONAS = load_personas(HERE / "personas.yaml")
MATRIX = yaml.safe_load((HERE / "matrix.yaml").read_text(encoding="utf-8"))
ROWS = MATRIX["rows"]


def per_stack(rows: list[dict], label) -> dict:
    """pytest.mark.parametrize arguments: each row once per stack of its persona."""
    cases = [(r, s) for r in rows for s in PERSONAS[r["persona"]].stacks]
    return {
        "argnames": ("row", "stack"),
        "argvalues": cases,
        "ids": [f"{s}:{label(r)}" for r, s in cases],
    }


@pytest.fixture(scope="module")
def snap(tmp_path_factory):
    config_dir = make_config_dir(tmp_path_factory.mktemp("cfg"), fixture_tools=False)
    return load_snapshot(config_dir, "local", TEST_ENV)


def _row_id(row: dict) -> str:
    args = ",".join(f"{k}={v}" for k, v in (row.get("args") or {}).items())
    return f"{row['persona']}:{row['tool']}({args})->{row['expect']}"


@pytest.mark.parametrize(**per_stack(ROWS, _row_id))
def test_matrix_row(snap, row, stack):
    policy = resolve_persona(snap, PERSONAS[row["persona"]], stack)
    decision = authorize(policy, row["tool"], row.get("args") or {})
    assert decision.allowed is (row["expect"] == "allow"), (decision.reason, decision.matched_rule)


def test_every_catalog_tool_has_matrix_rows(snap):
    covered = {row["tool"] for row in ROWS}
    assert not set(snap.tools) - covered, "add persona-matrix rows for new tools"


def test_matrix_references_known_personas_and_tools(snap):
    for row in ROWS:
        assert row["persona"] in PERSONAS, row
        assert row["tool"] in snap.tools, row
        assert row["expect"] in ("allow", "deny"), row


def test_personas_use_known_app_roles(snap):
    """Every persona app role is granted something in config, except the deliberately unknown
    one; the fixture-only SDLC.Infra.Reader comes from tests/support/config.py."""
    for persona in PERSONAS.values():
        unknown = set(persona.app_roles) - snap.app_role_values
        assert unknown <= {"SDLC.NotDefined"}, persona


def test_personas_use_known_groups(snap):
    """The same for Google groups (the fixture's until the repo config binds its own)."""
    for persona in PERSONAS.values():
        unknown = set(persona.groups) - snap.group_values
        assert unknown <= {f"sdlc-notdefined@{GOOGLE_DOMAIN}"}, persona


SKILL_ROWS = MATRIX["skill_rows"]


@pytest.mark.parametrize(
    **per_stack(SKILL_ROWS, lambda r: f"{r['persona']}:{r['skill']}->{r['expect']}")
)
def test_skill_row(snap, row, stack):
    policy = resolve_persona(snap, PERSONAS[row["persona"]], stack)
    assert policy.sees_skill(row["skill"]) is (row["expect"] == "visible"), policy.skills


def test_every_skill_has_matrix_rows(snap):
    covered = {row["skill"] for row in SKILL_ROWS}
    assert not set(snap.skills) - covered, "add skill_rows for new skills"


DATA_ROWS = MATRIX["data_rows"]


@pytest.mark.parametrize(
    **per_stack(DATA_ROWS, lambda r: f"{r['persona']}:{r['source']}->{r['expect']}")
)
def test_data_row(snap, row, stack):
    policy = resolve_persona(snap, PERSONAS[row["persona"]], stack)
    source = snap.sources[row["source"]]
    readable = source.id in policy.readable_sources
    assert readable is (row["expect"] == "readable"), (
        policy.data_sources,
        policy.max_classification,
    )


def test_every_source_has_matrix_rows(snap):
    covered = {row["source"] for row in DATA_ROWS}
    assert not set(snap.sources) - covered, "add data_rows for new sources"
