"""sdlc-config validate --check-secrets: every secret reference resolves; values never printed."""

from types import SimpleNamespace

from sdlc_config.cli import _check_secrets, main, secret_references
from sdlc_secrets import EnvSecretStore, SecretResolver

SECRET_VALUE = "ghp_do-not-print-me"


def snap_with(*sources):
    return SimpleNamespace(
        sources={s.id: s for s in sources},
    )


def source(sid, credentials=None):
    return SimpleNamespace(id=sid, credentials=credentials)


def test_references_are_collected_per_secret():
    snap = snap_with(
        source("a", ("secret", "github-token")),
        source("b", ("secret", "github-token")),
        source("c", ("env", "JIRA_TOKEN")),
        source("d"),
    )
    assert secret_references(snap) == {
        ("secret", "github-token"): ["sources/a.yaml", "sources/b.yaml"],
        ("env", "JIRA_TOKEN"): ["sources/c.yaml"],
    }


def test_all_resolve_and_no_value_is_printed(capsys):
    environ = {"SDLC_SECRET_GITHUB_TOKEN": SECRET_VALUE, "JIRA_TOKEN": SECRET_VALUE}
    resolver = SecretResolver(EnvSecretStore(environ), environ)
    snap = snap_with(source("a", ("secret", "github-token")), source("c", ("env", "JIRA_TOKEN")))
    assert _check_secrets(snap, resolver) == 0
    out = capsys.readouterr().out
    assert "secret:github-token ok" in out and "env:JIRA_TOKEN ok" in out
    assert "2/2 resolve" in out
    assert SECRET_VALUE not in out


def test_missing_reference_fails(capsys):
    resolver = SecretResolver(EnvSecretStore({}), {})
    snap = snap_with(source("a", ("secret", "github-token")))
    assert _check_secrets(snap, resolver) == 1
    out = capsys.readouterr().out
    assert "secret:github-token MISSING (used by sources/a.yaml)" in out
    assert "0/1 resolve" in out


def test_no_references(capsys):
    assert _check_secrets(snap_with(source("a"))) == 0
    assert "no secret references" in capsys.readouterr().out


def test_cli_flag_on_repo_config(config_dir, capsys):
    """The repo's sources use no credentials today, so the check passes without a backend."""
    argv = ["validate", "--config-dir", str(config_dir), "--dummy-env", "--check-secrets"]
    assert main(argv) == 0
    assert "secrets:" in capsys.readouterr().out
