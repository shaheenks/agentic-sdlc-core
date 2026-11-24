"""The permission diff (FR-CFG-002): who gains or loses which tools between two configuration versions."""

import json
import shutil
import subprocess

import pytest
import yaml
from sdlc_config import CONFIG_DIR, compile_config
from sdlc_config.cli import main
from sdlc_config.diff import UNLISTED, Change, diff


@pytest.fixture
def config_dir(tmp_path):
    target = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, target, ignore=shutil.ignore_patterns("src", "tests", "*.toml", "*.md", "local", "dev"))
    return target


def edit(path, change):
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(doc)
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")


def compiled(path):
    result = compile_config(path, "example")
    assert result.ok, result.problems
    return result.config


def add_grant(grant):
    return lambda d: d["grants"].append(grant)


def tool_group(tools):
    return lambda d: d["tool_groups"].update({"beta": {"description": "-", "tools": tools}})


def on_surface(*surfaces):
    def change(d):
        for s in surfaces:
            d["surfaces"][s]["tool_groups"].append("beta")

    return change


def test_no_change_means_no_diff():
    config = compiled(CONFIG_DIR)
    assert diff(config, config) == []


def test_a_user_group_grant_reaches_its_members_own_runs_only(config_dir):
    before = compiled(config_dir)
    edit(config_dir / "tool_groups.yaml", tool_group(["beta_tool"]))
    edit(config_dir / "surfaces.yaml", on_surface("sdlc_ui"))
    edit(
        config_dir / "grants.yaml",
        add_grant(
            {"id": "beta", "description": "-", "tool_groups": ["beta"], "to": {"user_groups": ["early-adopters"]}}
        ),
    )
    changes = diff(before, compiled(config_dir))
    # grace is an early adopter; her platform team is not granted the group, so its runs stay as they were.
    assert changes == [Change("grace@example.test", "own runs", "sdlc_ui", ("beta_tool",), ())]


def test_a_team_grant_reaches_the_team_runs_and_removing_it_is_a_loss(config_dir):
    edit(config_dir / "tool_groups.yaml", tool_group(["beta_tool"]))
    edit(config_dir / "surfaces.yaml", on_surface("sdlc_ui"))
    before = compiled(config_dir)
    edit(
        config_dir / "grants.yaml",
        add_grant({"id": "beta", "description": "-", "tool_groups": ["beta"], "to": {"teams": ["payments:lead"]}}),
    )
    after = compiled(config_dir)
    gained = {(c.user, c.context, c.surface): c.gained for c in diff(before, after)}
    assert gained == {
        ("ada@example.test", "own runs", "sdlc_ui"): ("beta_tool",),
        ("ada@example.test", "payments runs", "sdlc_ui"): ("beta_tool",),
    }
    assert {c.lost for c in diff(after, before)} == {("beta_tool",)}


def test_unlisted_users_and_blocking_are_shown(config_dir):
    before = compiled(config_dir)
    edit(
        config_dir / "env/example/blocked.yaml",
        lambda d: d["blocked"].append({"email": "Ada@example.test", "reason": "-"}),
    )
    edit(config_dir / "surfaces.yaml", lambda d: d["surfaces"]["user_agent"]["tool_groups"].remove("artifacts"))
    changes = diff(before, compiled(config_dir))
    ada = [c for c in changes if c.user == "ada@example.test"]
    assert ada and all(c.gained == () and c.lost for c in ada)  # blocked: everything goes
    unlisted = [c for c in changes if c.user == UNLISTED]
    assert [(c.surface, c.lost) for c in unlisted] == [
        ("user_agent", ("artifact_delete", "artifact_list", "artifact_read", "artifact_save"))
    ]
    assert changes[-1].user == UNLISTED  # listed users first


def test_cli_compares_two_folders(config_dir, tmp_path, capsys):
    base = tmp_path / "base"
    shutil.copytree(config_dir, base)
    edit(config_dir / "surfaces.yaml", lambda d: d["surfaces"]["user_agent"]["tool_groups"].remove("connections"))
    args = ["diff", "--env", "example", "--dir", str(config_dir), "--base", str(base)]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "Permission diff for env example" in out
    assert "  own runs, user_agent: - connection_list, connection_revoke, connection_start" in out


def test_cli_reads_published_bundles(config_dir, tmp_path, capsys):
    store = tmp_path / "store"
    assert main(["publish", "--env", "example", "--dir", str(config_dir), "--to", str(store), "--activate"]) == 0
    version = json.loads((store / "active.json").read_text())["version"]
    assert main(["diff", "--env", "example", "--dir", str(config_dir), "--base", f"{store}@active"]) == 0
    assert main(["diff", "--env", "example", "--base", f"{store}@{version}", "--head", str(config_dir)]) == 0
    out = capsys.readouterr().out
    assert out.count("No one gains or loses a tool.") == 2


def test_cli_reads_a_git_revision(capsys):
    try:
        subprocess.run(["git", "rev-parse", "HEAD"], cwd=CONFIG_DIR, check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not in a git checkout")
    assert main(["diff", "--env", "example", "--base", "git:HEAD"]) == 0
    assert "Permission diff for env example: git:HEAD -> working tree" in capsys.readouterr().out


def test_cli_reports_an_unreadable_version(tmp_path, capsys):
    assert main(["diff", "--env", "example", "--base", f"{tmp_path}@nope"]) == 1
    assert "error:" in capsys.readouterr().err
