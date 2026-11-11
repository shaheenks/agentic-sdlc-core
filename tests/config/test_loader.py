import shutil
from pathlib import Path

import pytest
from sdlc_config import ConfigError, ConfigStore, load_snapshot
from sdlc_config.cli import main as cli_main

REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"
TENANT = "11111111-2222-3333-4444-555555555555"
API_CLIENT = "66666666-7777-8888-9999-000000000000"
ENV = {"ENTRA_TENANT_ID": TENANT, "ENTRA_API_CLIENT_ID": API_CLIENT}


def test_repo_config_loads(config_dir):
    snap = load_snapshot(config_dir, "local", ENV)
    assert snap.platform.tenant_id == TENANT
    assert snap.platform.issuer == f"https://login.microsoftonline.com/{TENANT}/v2.0"
    assert snap.platform.audience == (API_CLIENT, f"api://{API_CLIENT}")
    assert snap.platform.required_scopes == ("access_as_user",)
    assert {"SDLC.User", "SDLC.Admin", "SDLC.Payments.Member"} <= snap.app_role_values
    assert snap.version.startswith("local-")


def test_missing_env_var_fails_closed(config_dir):
    with pytest.raises(ConfigError, match="ENTRA_TENANT_ID is not set"):
        load_snapshot(config_dir, "local", {"ENTRA_API_CLIENT_ID": API_CLIENT})


def test_dummy_env_allows_structure_check(config_dir):
    snap = load_snapshot(config_dir, "local", {}, dummy_env=True)
    assert snap.platform.tenant_id == "00000000-0000-0000-0000-000000000000"


def test_unknown_key_fails(config_dir):
    p = config_dir / "platform.yaml"
    p.write_text(p.read_text() + "surprise: true\n")
    with pytest.raises(ConfigError, match="surprise"):
        load_snapshot(config_dir, "local", ENV)


def test_default_classification_must_exist(config_dir):
    p = config_dir / "platform.yaml"
    p.write_text(p.read_text().replace("max_classification: public", "max_classification: secret"))
    with pytest.raises(ConfigError, match="max_classification 'secret'"):
        load_snapshot(config_dir, "local", ENV)


def test_missing_env_folder_fails(config_dir):
    with pytest.raises(ConfigError, match="env/nowhere: unknown environment"):
        load_snapshot(config_dir, "nowhere", ENV)


def test_env_without_tenant_files_loads(config_dir):
    """CH-0011: no group map; users.yaml and blocked.yaml are optional."""
    assert load_snapshot(config_dir, "prod", ENV).users.alias_by_oid == {}


def test_group_identities_fail_with_a_clear_message(config_dir):
    p = config_dir / "roles.yaml"
    text = p.read_text().replace(
        "bindings:\n", "bindings:\n  - group: eng-all\n    roles: [viewer]\n", 1
    )
    p.write_text(text)
    with pytest.raises(ConfigError, match=r"bindings\[0\]/group: Entra groups are no longer used"):
        load_snapshot(config_dir, "local", ENV)


def test_a_leftover_groups_file_is_ignored(config_dir):
    v1 = load_snapshot(config_dir, "local", ENV).version
    (config_dir / "env/local/groups.yaml").write_text("not: [valid yaml for anything\n")
    assert load_snapshot(config_dir, "local", ENV).version == v1


def test_errors_are_all_reported_at_once(config_dir):
    (config_dir / "platform.yaml").write_text("apiVersion: sdlc/v1\nkind: Platform\n")
    with pytest.raises(ConfigError) as exc:
        load_snapshot(config_dir, "local", ENV)
    assert len(exc.value.problems) >= 3


def test_version_changes_with_content(config_dir):
    v1 = load_snapshot(config_dir, "local", ENV).version
    assert load_snapshot(config_dir, "local", ENV).version == v1
    p = config_dir / "env/local/users.yaml"
    p.write_text(p.read_text() + "\n# comment\n")
    assert load_snapshot(config_dir, "local", ENV).version != v1


def test_store_fails_closed_at_startup(config_dir):
    (config_dir / "platform.yaml").unlink()
    with pytest.raises(ConfigError):
        ConfigStore(lambda: load_snapshot(config_dir, "local", ENV))


def test_store_keeps_last_known_good_and_notifies(config_dir):
    store = ConfigStore(lambda: load_snapshot(config_dir, "local", ENV))
    good = store.current()
    seen = []
    store.subscribe(lambda snap: seen.append(snap.version))

    (config_dir / "platform.yaml").write_text("kind: Broken\n")
    assert store.reload() is False
    assert store.current() is good
    assert "expected kind 'Platform'" in store.last_error

    shutil.copy(REPO_CONFIG / "platform.yaml", config_dir / "platform.yaml")
    p = config_dir / "env/local/users.yaml"
    p.write_text(p.read_text() + "\n# changed\n")
    assert store.reload() is True
    assert store.current().version != good.version
    assert seen == [store.current().version]
    assert store.last_error is None


def test_cli_validate(config_dir, monkeypatch, capsys):
    monkeypatch.delenv("ENTRA_TENANT_ID", raising=False)
    assert cli_main(["validate", "--config-dir", str(config_dir)]) == 1
    assert "ENTRA_TENANT_ID" in capsys.readouterr().err
    assert cli_main(["validate", "--config-dir", str(config_dir), "--dummy-env"]) == 0
    assert capsys.readouterr().out.startswith("OK env=local")
