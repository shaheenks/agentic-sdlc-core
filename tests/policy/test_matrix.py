"""Stage 3f: persona matrix (tests/policy/matrix.yaml) against the repo config."""

from pathlib import Path

import pytest
import yaml
from sdlc_config import load_snapshot, resolve
from sdlc_config.personas import load_personas
from sdlc_policy import authorize

from tests.support.config import make_config_dir
from tests.support.entra import TEST_ENV

HERE = Path(__file__).parent
PERSONAS = load_personas(HERE / "personas.yaml")
ROWS = yaml.safe_load((HERE / "matrix.yaml").read_text(encoding="utf-8"))["rows"]


@pytest.fixture(scope="module")
def snap(tmp_path_factory):
    return load_snapshot(make_config_dir(tmp_path_factory.mktemp("cfg")), "local", TEST_ENV)


def _row_id(row: dict) -> str:
    args = ",".join(f"{k}={v}" for k, v in (row.get("args") or {}).items())
    return f"{row['persona']}:{row['tool']}({args})->{row['expect']}"


@pytest.mark.parametrize("row", ROWS, ids=[_row_id(r) for r in ROWS])
def test_matrix_row(snap, row):
    persona = PERSONAS[row["persona"]]
    policy = resolve(snap, persona.groups, persona.app_roles)
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


def test_personas_use_known_group_aliases(snap):
    known = set(snap.groups.alias_by_id.values())
    for persona in PERSONAS.values():
        assert set(persona.groups) <= known, persona
