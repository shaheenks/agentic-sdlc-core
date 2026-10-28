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
        lambda d: d["spec"].update(location="https://github.com/acme/repo.git", provider="github"),
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
        lambda d: d["spec"].update(
            location="https://x:token@github.com/acme/repo.git", provider="github"
        ),
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


def test_credentials_are_kept_as_references(config_dir):
    edit_yaml(
        config_dir / "platform.yaml",
        lambda d: d["knowledge"].update(allowed_hosts=["github.com"]),
    )
    edit_yaml(
        config_dir / "sources/sdlc-platform.yaml",
        lambda d: d["spec"].update(
            location="https://github.com/acme/repo.git",
            provider="github",
            credentials={"secret": "github-sdlc-token"},
        ),
    )
    source = load(config_dir).sources["sdlc-platform"]
    assert source.credentials == ("secret", "github-sdlc-token")
    assert source.provider == "github"


def test_allowed_hosts_schema(config_dir):
    edit_yaml(
        config_dir / "platform.yaml",
        lambda d: d["knowledge"].update(allowed_hosts=["https://github.com"]),
    )
    with pytest.raises(ConfigError, match="allowed_hosts"):
        load(config_dir)


# --- version-01 M1: remote git providers ----------------------------------------------------------


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        ({"location": "https://github.com/acme/repo.git"}, "spec/provider: required"),
        ({"provider": "github"}, "spec/provider: only for git sources with an https location"),
        ({"credentials": {"env": "GITHUB_TOKEN"}}, "only https git sources use credentials"),
        (
            {"location": "https://github.com/acme/team/repo.git", "provider": "github"},
            "expected https://github.com/<owner>/<repo>.git",
        ),
        (
            {"location": "https://github.com/acme/repo.git", "provider": "bitbucket-cloud"},
            "bitbucket-cloud repositories are on bitbucket.org",
        ),
        (
            {
                "location": "https://bb.example.com/projects/PAY/repo.git",
                "provider": "bitbucket-dc",
            },
            "/scm/<project>/<repo>.git",
        ),
        ({"location": "https://github.com/acme/repo.git", "provider": "gitlab"}, "spec/provider"),
    ],
)
def test_bad_remote_git_sources_fail(config_dir, spec, message):
    edit_yaml(
        config_dir / "platform.yaml",
        lambda d: d["knowledge"].update(allowed_hosts=["github.com", "bb.example.com"]),
    )
    edit_yaml(config_dir / "sources/sdlc-platform.yaml", lambda d: d["spec"].update(spec))
    with pytest.raises(ConfigError) as exc:
        load(config_dir)
    assert message in str(exc.value), exc.value


@pytest.mark.parametrize(
    ("location", "provider"),
    [
        ("https://github.com/acme/repo.git", "github"),
        ("https://bitbucket.org/ws/repo.git", "bitbucket-cloud"),
        ("https://bb.example.com/scm/pay/repo.git", "bitbucket-dc"),
        ("https://bb.example.com/bitbucket/scm/pay/repo.git", "bitbucket-dc"),
    ],
)
def test_remote_git_sources_load(config_dir, location, provider):
    edit_yaml(
        config_dir / "platform.yaml",
        lambda d: d["knowledge"].update(
            allowed_hosts=["github.com", "bitbucket.org", "bb.example.com"]
        ),
    )
    edit_yaml(
        config_dir / "sources/sdlc-platform.yaml",
        lambda d: d["spec"].update(
            location=location, provider=provider, ref="main", credentials={"secret": "repo-token"}
        ),
    )
    source = load(config_dir).sources["sdlc-platform"]
    assert (source.provider, source.ref, source.credentials) == (
        provider,
        "main",
        ("secret", "repo-token"),
    )
