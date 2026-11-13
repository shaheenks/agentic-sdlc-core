"""The Agent Gateway's tool allowlist comes from config (CH-0015, NFR-SEC-015)."""

import json
from pathlib import Path

import pytest
from sdlc_config import load_snapshot
from sdlc_config.cli import main
from sdlc_config.gateway import gateway_policy, render

from tests.support.config import REPO_ROOT, make_config_dir
from tests.support.entra import TEST_ENV

POLICY_FILE = REPO_ROOT / "infra" / "gcp" / "generated" / "gateway_policy.json"


@pytest.fixture
def snap(tmp_path):
    return load_snapshot(make_config_dir(tmp_path, fixture_tools=False), "local", TEST_ENV)


def test_allowlist_is_the_servers_catalog(snap):
    policy = gateway_policy(snap)
    served = sorted(n for n, t in snap.tools.items() if t.server == "core-mcp")
    assert policy["tools"] == served
    assert [t["name"] for t in policy["toolspec"]["tools"]] == served
    assert all(t["inputSchema"] == {"type": "object"} for t in policy["toolspec"]["tools"])


def test_unknown_server_is_refused(snap):
    with pytest.raises(ValueError, match="no tools for server 'impl-mcp'"):
        gateway_policy(snap, "impl-mcp")


def test_checked_in_policy_matches_config():
    """The file Terraform reads equals what config generates: the gateway never allows a tool
    config does not have, and a new tool fails here until the file is regenerated."""
    assert main(["gateway-policy", "--dummy-env", "--check", str(POLICY_FILE)]) == 0


def test_drift_is_reported(tmp_path, capsys):
    stale = tmp_path / "gateway_policy.json"
    policy = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
    policy["tools"].append("drop_database")
    stale.write_text(render(policy), encoding="utf-8")
    assert main(["gateway-policy", "--dummy-env", "--check", str(stale)]) == 1
    assert "differs from config" in capsys.readouterr().out


def test_output_is_stable(tmp_path):
    out = Path(tmp_path) / "p.json"
    assert main(["gateway-policy", "--dummy-env", "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == POLICY_FILE.read_text(encoding="utf-8")
