"""Config bundles (H4 / Stage 7b local store): compile, verify, activate, reload, rollback."""

import json
from pathlib import Path

import pytest
import yaml
from sdlc_config import ConfigError, ConfigStore, load_snapshot
from sdlc_config.bundles import (
    activate,
    compile_bundle,
    current_version,
    list_bundles,
    load_bundle,
    verify_bundle,
)
from sdlc_config.cli import main

from tests.support.entra import TEST_ENV

ENV = {**TEST_ENV, "SDLC_CONFIG_GIT_SHA": "0123456789ab"}


def compile_(config_dir: Path, root: Path) -> str:
    version, _ = compile_bundle(config_dir, "local", root, environ=ENV)
    return version


def change_tool_risk(config_dir: Path) -> None:
    path = config_dir / "tools.yaml"
    doc = yaml.safe_load(path.read_text())
    doc["tools"]["ping"]["risk"] = "medium" if doc["tools"]["ping"]["risk"] == "low" else "low"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def test_compile_writes_an_immutable_verified_bundle(config_dir, tmp_path):
    root = tmp_path / "bundles"
    version, created = compile_bundle(config_dir, "local", root, environ=ENV)
    assert created and version.startswith("0123456789ab-")
    assert compile_bundle(config_dir, "local", root, environ=ENV) == (version, False)
    manifest = verify_bundle(root, version)
    assert manifest["env"] == "local" and manifest["git_sha"] == "0123456789ab"
    files = set(manifest["files"])
    assert {"config/platform.yaml", "config/env/local/groups.yaml"} <= files
    assert any(f.startswith("skills/") and f.endswith("/SKILL.md") for f in files)
    assert any(f.startswith("config/schemas/") for f in files)
    source = load_snapshot(config_dir, "local", ENV)
    assert load_bundle(root, "local", version, environ=ENV).version == source.version == version


def test_bundle_keeps_placeholders_not_secret_values(config_dir, tmp_path):
    root = tmp_path / "bundles"
    version = compile_(config_dir, root)
    platform = (root / version / "tree/config/platform.yaml").read_text()
    assert "${ENTRA_TENANT_ID}" in platform
    assert ENV["ENTRA_TENANT_ID"] not in platform


def test_content_change_means_a_new_version(config_dir, tmp_path):
    root = tmp_path / "bundles"
    first = compile_(config_dir, root)
    change_tool_risk(config_dir)
    second = compile_(config_dir, root)
    assert first != second and {m["version"] for m in list_bundles(root)} == {first, second}


@pytest.mark.parametrize(
    ("tamper", "message"),
    [
        (lambda b: (b / "tree/config/tools.yaml").write_text("tampered"), "does not match"),
        (lambda b: (b / "tree/config/extra.yaml").write_text("x: 1"), "unexpected file"),
        (lambda b: (b / "tree/config/roles.yaml").unlink(), "missing file"),
    ],
)
def test_tampered_bundles_are_rejected(config_dir, tmp_path, tamper, message):
    root = tmp_path / "bundles"
    version = compile_(config_dir, root)
    tamper(root / version)
    with pytest.raises(ConfigError, match=message):
        load_bundle(root, "local", version, environ=ENV)
    with pytest.raises(ConfigError, match=message):  # the pointer never moves to it
        activate(root, version)


def test_env_mismatch_is_rejected(config_dir, tmp_path):
    root = tmp_path / "bundles"
    version = compile_(config_dir, root)
    with pytest.raises(ConfigError, match="for env 'local', not 'prod'"):
        activate(root, version, env="prod")
    with pytest.raises(ConfigError, match="for env 'local', not 'prod'"):
        load_bundle(root, "prod", version, environ=ENV)


def test_store_fails_closed_without_a_valid_pointer(tmp_path, monkeypatch):
    root = tmp_path / "bundles"
    root.mkdir()
    with pytest.raises(ConfigError, match="no active bundle"):
        ConfigStore.from_bundles(root, "local")
    (root / "current").write_text("../../etc")
    with pytest.raises(ConfigError, match="invalid bundle version"):
        ConfigStore.from_bundles(root, "local")


def test_store_reloads_on_activate_and_rolls_back(config_dir, tmp_path, monkeypatch):
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    root = tmp_path / "bundles"
    first = compile_(config_dir, root)
    activate(root, first)
    store = ConfigStore.from_bundles(root, "local")
    assert store.current().version == first

    change_tool_risk(config_dir)
    second = compile_(config_dir, root)
    activate(root, second)
    assert store.reload() and store.current().version == second

    activate(root, first)  # rollback = point back
    assert store.reload() and store.current().version == first
    assert current_version(root) == first


def test_broken_bundle_on_reload_keeps_last_known_good(config_dir, tmp_path, monkeypatch):
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    root = tmp_path / "bundles"
    good = compile_(config_dir, root)
    activate(root, good)
    store = ConfigStore.from_bundles(root, "local")
    change_tool_risk(config_dir)
    bad = compile_(config_dir, root)
    (root / bad / "tree/config/tools.yaml").write_text("tampered")
    (root / "current").write_text(bad)  # pointer forced past `activate`'s verification
    assert store.reload() is False
    assert store.current().version == good and "does not match" in store.last_error


def test_from_env_prefers_bundles(config_dir, tmp_path, monkeypatch):
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    root = tmp_path / "bundles"
    version = compile_(config_dir, root)
    activate(root, version)
    monkeypatch.setenv("SDLC_CONFIG_BUNDLES", str(root))
    monkeypatch.setenv("SDLC_ENV", "local")
    assert ConfigStore.from_env().current().version == version


def test_cli_compile_activate_and_list(config_dir, tmp_path, monkeypatch, capsys):
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    root = tmp_path / "bundles"
    args = ["--env", "local", "--config-dir", str(config_dir), "--out", str(root)]
    assert main(["compile", *args, "--activate"]) == 0
    first = current_version(root)
    change_tool_risk(config_dir)
    assert main(["compile", *args]) == 0
    assert current_version(root) == first  # compile alone does not activate
    second = next(m["version"] for m in list_bundles(root) if m["version"] != first)
    assert main(["activate", second, "--root", str(root), "--env", "local"]) == 0
    capsys.readouterr()
    assert main(["bundles", "--root", str(root)]) == 0
    listing = capsys.readouterr().out
    assert f"* {second}" in listing and f"  {first}" in listing
    manifest = json.loads((root / second / "manifest.json").read_text())
    assert manifest["version"] == second
