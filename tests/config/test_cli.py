"""Stage 3e: sdlc-config explain / diff."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from sdlc_config.cli import main

from tests.support.config import TEST_USERS_YAML

PERSONAS = Path(__file__).resolve().parents[1] / "policy" / "personas.yaml"


def run(capsys, *argv) -> tuple[int, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def test_explain_persona(config_dir, capsys):
    code, out = run(
        capsys,
        "explain",
        "--persona",
        "payments-member",
        "--personas",
        str(PERSONAS),
        "--config-dir",
        str(config_dir),
        "--dummy-env",
    )
    assert code == 0
    assert "payments       <- teams/payments.yaml#membership[0]" in out
    assert re.search(r"fixture_review +repo in \[payments-api, payments-ui\]", out)


def test_explain_app_roles_json_reports_unknown(config_dir, capsys):
    code, out = run(
        capsys,
        "explain",
        "--app-roles",
        "SDLC.User,SDLC.Ghosts",
        "--json",
        "--config-dir",
        str(config_dir),
        "--dummy-env",
    )
    view = json.loads(out)
    assert code == 0 and view["unknown"] == ["app_role:SDLC.Ghosts"]
    assert set(view["tools"]) >= {"whoami", "list_skills"} and "fixture_review" not in view["tools"]


def test_explain_unknown_persona_fails(config_dir, capsys):
    code, out = run(
        capsys,
        "explain",
        "--persona",
        "wizard",
        "--personas",
        str(PERSONAS),
        "--config-dir",
        str(config_dir),
        "--dummy-env",
    )
    assert code == 1 and "unknown persona 'wizard'" in out


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_diff_between_revisions(tmp_path, config_dir, capsys):
    repo = tmp_path / "repo"
    shutil.copytree(config_dir, repo / "config")
    shutil.copytree(config_dir.parent / "skills", repo / "skills")  # config references skills/
    (repo / ".gitignore").write_text("config/env/*/users.yaml\n")
    git = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]
    subprocess.run([*git, "init", "-q"], cwd=repo, check=True)
    subprocess.run([*git, "add", "-A"], cwd=repo, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "base"], cwd=repo, check=True)
    assert (repo / "config/env/local/users.yaml").read_text() == TEST_USERS_YAML  # ignored

    team = repo / "config/teams/payments.yaml"
    team.write_text(
        team.read_text().replace(
            "repo: { in: [payments-api, payments-ui] }",
            "repo: { in: [payments-api, payments-ui, payments-ledger] }",
            1,
        )
    )
    roles = repo / "config/roles.yaml"
    roles.write_text(
        roles.read_text().replace("tools:  { allow: [fixture_approve] }", "tools:  { allow: [] }")
    )

    code, out = run(
        capsys,
        "diff",
        "--from",
        "HEAD",
        "--config-dir",
        str(repo / "config"),
        "--personas",
        str(PERSONAS),
        "--exit-code",
    )
    assert code == 1
    assert (
        "payments-member:\n  ~ fixture_review  (repo in [payments-api, payments-ui] -> "
        "repo in [payments-api, payments-ledger, payments-ui])" in out
    )
    assert "payments-approver:" in out and "  - fixture_approve" in out
    assert "platform-member:" not in out  # unchanged personas are not listed

    code, out = run(
        capsys,
        "diff",
        "--from",
        "HEAD",
        "--to",
        "HEAD",
        "--config-dir",
        str(repo / "config"),
        "--personas",
        str(PERSONAS),
    )
    assert code == 0 and "no permission changes" in out
