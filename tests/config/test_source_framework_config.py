"""version-01 M0: source credentials (references only) and the remote host allowlist."""

import pytest
import yaml
from sdlc_config import ConfigError, load_snapshot
from sdlc_config.hosts import host_allowed, url_allowed, url_host

from tests.support.entra import TEST_ENV


def load(config_dir):
    return load_snapshot(config_dir, "local", TEST_ENV)


def edit_yaml(path, mutate):
    doc = yaml.safe_load(path.read_text())
    mutate(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


@pytest.mark.parametrize(
    ("host", "allowed", "expected"),
    [
        ("github.com", ["github.com"], True),
        ("GitHub.com", ["github.com"], True),
        ("api.github.com", ["github.com"], False),
        ("acme.atlassian.net", ["*.atlassian.net"], True),
        ("atlassian.net", ["*.atlassian.net"], False),
        ("a.b.atlassian.net", ["*.atlassian.net"], False),  # one label only
        ("evilatlassian.net", ["*.atlassian.net"], False),
        ("", ["*.atlassian.net"], False),
        ("github.com", [], False),
    ],
)
def test_host_allowed(host, allowed, expected):
    assert host_allowed(host, allowed) is expected


@pytest.mark.parametrize(
    ("url", "host"),
    [
        ("https://github.com/org/repo.git", "github.com"),
        ("https://github.com:443/org/repo", "github.com"),
        ("http://github.com/org/repo", None),
        ("https://user:pw@github.com/org/repo", None),  # credentials never go in URLs
        ("ssh://git@github.com/org/repo", None),
        ("not a url", None),
    ],
)
def test_url_host(url, host):
    assert url_host(url) == host
    assert url_allowed(url, ["github.com"]) is (host is not None)


def test_https_source_needs_an_allowed_host(config_dir):
    edit_yaml(
        config_dir / "sources/sdlc-platform.yaml",
        lambda d: d["spec"].update(location="https://github.com/acme/repo.git"),
    )
    with pytest.raises(ConfigError, match="host 'github.com' is not in platform.yaml"):
        load(config_dir)
    edit_yaml(
        config_dir / "platform.yaml",
        lambda d: d["knowledge"].update(allowed_hosts=["github.com", "*.atlassian.net"]),
    )
    snap = load(config_dir)
    assert snap.platform.allowed_hosts == ("github.com", "*.atlassian.net")
    assert snap.sources["sdlc-platform"].location == "https://github.com/acme/repo.git"


def test_credentials_in_urls_are_refused(config_dir):
    edit_yaml(
        config_dir / "platform.yaml",
        lambda d: d["knowledge"].update(allowed_hosts=["github.com"]),
    )
    edit_yaml(
        config_dir / "sources/sdlc-platform.yaml",
        lambda d: d["spec"].update(location="https://x:token@github.com/acme/repo.git"),
    )
    with pytest.raises(ConfigError, match="no credentials in URLs"):
        load(config_dir)


@pytest.mark.parametrize(
    ("credentials", "message"),
    [
        ({"value": "abc"}, "spec/credentials"),  # only references, never values
        ({"env": "lower"}, "spec/credentials"),
        ({"secret": "Bad_Name"}, "spec/credentials"),
        ({"env": "A", "secret": "a"}, "spec/credentials"),
        ({"env": "PAYMENTS_TOKEN"}, "local_folder sources take no credentials"),
    ],
)
def test_bad_credentials_fail(config_dir, credentials, message):
    edit_yaml(
        config_dir / "sources/payments-code.yaml",
        lambda d: d["spec"].update(credentials=credentials),
    )
    with pytest.raises(ConfigError) as exc:
        load(config_dir)
    assert message in str(exc.value), exc.value


def test_credentials_are_kept_as_references(config_dir, monkeypatch):
    from sdlc_config import loader

    monkeypatch.setattr(loader, "CREDENTIAL_SOURCE_TYPES", frozenset({"git"}))
    edit_yaml(
        config_dir / "sources/sdlc-platform.yaml",
        lambda d: d["spec"].update(credentials={"secret": "github-sdlc-token"}),
    )
    assert load(config_dir).sources["sdlc-platform"].credentials == ("secret", "github-sdlc-token")


def test_allowed_hosts_schema(config_dir):
    edit_yaml(
        config_dir / "platform.yaml",
        lambda d: d["knowledge"].update(allowed_hosts=["https://github.com"]),
    )
    with pytest.raises(ConfigError, match="allowed_hosts"):
        load(config_dir)
