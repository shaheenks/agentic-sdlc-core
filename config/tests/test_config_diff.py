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


def give(kind, name, **given):
    return lambda d: d[kind][name].update(given)


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
    edit(config_dir / "env/example/user_groups.yaml", give("user_groups", "early-adopters", tool_groups=["beta"]))
    changes = diff(before, compiled(config_dir))
    # grace is listed as an early adopter, ada joins through payments:lead; their team runs stay as they were.
    assert changes == [
        Change("ada@example.test", "own runs", "sdlc_ui", ("beta_tool",), ()),
        Change("grace@example.test", "own runs", "sdlc_ui", ("beta_tool",), ()),
    ]


def test_a_team_grant_reaches_the_team_runs_and_removing_it_is_a_loss(config_dir):
    edit(config_dir / "tool_groups.yaml", tool_group(["beta_tool"]))
    edit(config_dir / "surfaces.yaml", on_surface("sdlc_ui"))
    before = compiled(config_dir)
    edit(
        config_dir / "env/example/teams/payments.yaml",
        lambda d: d["role_grants"]["lead"].update(tool_groups=["beta"]),
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
    assert all("source:platform-spec" in c.lost for c in ada)
    assert changes[-1].user == UNLISTED  # listed users first


def test_sources_granted_to_a_team_show_in_its_members_rows(config_dir):
    spec = yaml.safe_load((config_dir / "env/example/sources/platform-spec.yaml").read_text(encoding="utf-8"))
    spec = {k: v for k, v in spec.items() if k != "everyone"} | {"name": "Payments", "location": "payments"}
    (config_dir / "env/example/sources/payments-repo.yaml").write_text(yaml.safe_dump(spec), encoding="utf-8")
    before = compiled(config_dir)
    edit(config_dir / "env/example/teams/payments.yaml", lambda d: d.update(sources=["payments-repo"]))
    rows = {(c.user, c.context, c.surface): c.gained for c in diff(before, compiled(config_dir))}
    assert rows[("ada@example.test", "payments runs", "user_agent")] == ("source:payments-repo",)
    assert all(user == "ada@example.test" for user, _, _ in rows)


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
    assert out.count("No one gains or loses a tool or knowledge source.") == 2


def test_cli_reads_a_git_revision(config_dir, capsys):
    repo = config_dir.parent

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    try:
        git("init", "-q")
        git("add", "config")
        git("-c", "user.name=t", "-c", "user.email=t@example.test", "commit", "-q", "-m", "base")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git is not available")
    edit(config_dir / "surfaces.yaml", lambda d: d["surfaces"]["user_agent"]["tool_groups"].remove("identity"))
    assert main(["diff", "--env", "example", "--dir", str(config_dir), "--base", "git:HEAD"]) == 0
    out = capsys.readouterr().out
    assert "Permission diff for env example: git:HEAD -> working tree" in out
    assert "own runs, user_agent: - whoami" in out


def test_cli_reports_an_unreadable_version(tmp_path, capsys):
    assert main(["diff", "--env", "example", "--base", f"{tmp_path}@nope"]) == 1
    assert "error:" in capsys.readouterr().err


def test_a_team_in_a_user_group_gets_the_group_grants_in_own_runs_only(config_dir):
    edit(config_dir / "tool_groups.yaml", tool_group(["beta_tool"]))
    edit(config_dir / "surfaces.yaml", on_surface("sdlc_ui"))
    edit(config_dir / "env/example/user_groups.yaml", give("user_groups", "early-adopters", teams=[]))
    before = compiled(config_dir)
    edit(
        config_dir / "env/example/user_groups.yaml",
        give("user_groups", "early-adopters", teams=["payments"], tool_groups=["beta"]),
    )
    changes = diff(before, compiled(config_dir))
    # grace (listed) and ada (via payments) gain it in their own runs; no team run changes.
    assert {(c.user, c.context) for c in changes} == {
        ("ada@example.test", "own runs"),
        ("grace@example.test", "own runs"),
    }
