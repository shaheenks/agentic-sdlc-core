import json
import shutil

import pytest
import yaml
from sdlc_config import CONFIG_DIR, compile_config
from sdlc_config.cli import main


@pytest.fixture
def config_dir(tmp_path):
    """A copy of the repository's configuration, to change in a test."""
    target = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, target, ignore=shutil.ignore_patterns("src", "tests", "*.toml", "*.md", "local", "dev"))
    return target


def edit(path, change):
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(doc)
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")


def test_repository_config_validates_for_the_example_environment(capsys):
    assert main(["validate", "--env", "example"]) == 0
    assert "config ok" in capsys.readouterr().out


def test_compiled_config_lists_members_with_their_roles():
    config = compile_config(CONFIG_DIR, "example").config
    assert config["members"]["ada@example.test"] == {"teams": {"payments": ["lead", "member"]}, "user_groups": []}
    assert config["members"]["grace@example.test"]["user_groups"] == ["early-adopters"]
    assert config["identity"]["mode"] == "caller_token"
    assert config["identity"]["callers"]["sdlc_ui"] == ["sdlc-ui@example-project.iam.gserviceaccount.com"]


def test_trusted_header_is_refused_outside_local(config_dir, capsys):
    edit(config_dir / "env/example/identity.yaml", lambda d: d.update({"mode": "trusted_header"}))
    assert main(["validate", "--env", "example", "--dir", str(config_dir)]) == 1
    assert "only in the local environment" in capsys.readouterr().err


def test_missing_environment_warns_but_validates(config_dir, capsys):
    assert main(["validate", "--env", "nowhere", "--dir", str(config_dir)]) == 0
    assert "refuse every user" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("file", "change", "message"),
    [
        ("grants.yaml", lambda d: d["grants"][0]["to"].update({"teams": ["nope"]}), "unknown team 'nope'"),
        ("grants.yaml", lambda d: d["grants"][0]["to"].update({"teams": ["payments:boss"]}), "has no role 'boss'"),
        ("grants.yaml", lambda d: d["grants"][0]["tool_groups"].append("ghost"), "unknown tool group 'ghost'"),
        ("surfaces.yaml", lambda d: d["surfaces"]["sdlc_ui"]["tool_groups"].append("ghost"), "unknown tool group"),
        ("surfaces.yaml", lambda d: d["surfaces"]["sdlc_ui"].pop("description"), "'description' is a required"),
        ("env/example/identity.yaml", lambda d: d["callers"].update({"desktop": ["x"]}), "unknown surface 'desktop'"),
        (
            "env/example/identity.yaml",
            lambda d: d["callers"]["user_agent"].append(d["callers"]["sdlc_ui"][0]),
            "is in",
        ),
        (
            "env/example/users.yaml",
            lambda d: d["users"]["ada@example.test"]["teams"].append("payments:boss"),
            "no role",
        ),
        (
            "env/example/users.yaml",
            lambda d: d["users"]["ada@example.test"].update({"teams": ["nope"]}),
            "unknown team",
        ),
        (
            "env/example/users.yaml",
            lambda d: d["users"]["ada@example.test"].update({"user_groups": ["ghosts"]}),
            "unknown user group 'ghosts'",
        ),
        ("tool_groups.yaml", lambda d: d["tool_groups"]["identity"]["tools"].append("artifact_list"), "in both"),
    ],
)
def test_invalid_configuration_fails(config_dir, file, change, message, capsys):
    edit(config_dir / file, change)
    assert main(["validate", "--env", "example", "--dir", str(config_dir)]) == 1
    assert message in capsys.readouterr().err


def test_broken_yaml_fails(config_dir):
    (config_dir / "grants.yaml").write_text("grants: [1, 2", encoding="utf-8")
    assert main(["validate", "--env", "example", "--dir", str(config_dir)]) == 1


def test_publish_activate_and_roll_back(tmp_path, config_dir, capsys):
    store = tmp_path / "bundles"
    assert main(["publish", "--env", "example", "--to", str(store), "--activate", "--by", "tester"]) == 0
    first = json.loads((store / "active.json").read_text())["version"]

    edit(config_dir / "limits.yaml", lambda d: d["rate_limits"]["tool_calls"].update({"per_user_per_minute": 5}))
    assert main(["publish", "--env", "example", "--dir", str(config_dir), "--to", str(store), "--activate"]) == 0
    pointer = json.loads((store / "active.json").read_text())
    assert pointer["version"] != first and pointer["previous"] == first

    assert main(["activate", "--env", "example", "--to", str(store), "--version", first, "--by", "tester"]) == 0
    assert json.loads((store / "active.json").read_text())["version"] == first
    assert len(list((store / "activations").iterdir())) == 3
    assert '"event": "config.activate"' in capsys.readouterr().out


def test_activate_refuses_a_bundle_of_another_environment(tmp_path, config_dir):
    store = tmp_path / "bundles"
    assert main(["publish", "--env", "example", "--to", str(store)]) == 0
    version = next((store / "bundles").iterdir()).stem
    assert main(["activate", "--env", "dev", "--to", str(store), "--version", version]) == 1
    assert not (store / "active.json").exists()
