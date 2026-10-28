"""version-01 M1: remote git (GitHub, Bitbucket Cloud/DC): auth headers, deep links, branch
tracking and incremental reads.

No network: an `https://github.com/...` location is mapped to a local bare repository with git's
`url.<base>.insteadOf` (GIT_CONFIG_GLOBAL), so the real clone/fetch code path runs.
"""

import base64
import subprocess

import pytest
from sdlc_loaders import LoaderError
from sdlc_loaders.files import remote_git_env
from sdlc_loaders.git import GitLoader, auth_header, deep_link
from sdlc_secrets import EnvSecretStore, SecretResolver

URL = "https://github.com/acme/repo.git"
TOKEN = "ghs_test_token_value"  # noqa: S105 (test value)


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def upstream(tmp_path, monkeypatch):
    """A bare 'remote' plus a work tree to push commits from; URL maps to the bare repo."""
    bare, work = tmp_path / "remote.git", tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    git(bare, "config", "uploadpack.allowFilter", "true")
    git(bare, "config", "uploadpack.allowAnySHA1InWant", "true")
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    git(work, "remote", "add", "origin", str(bare))
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text(f'[url "{bare.as_uri()}"]\n\tinsteadOf = {URL}\n')
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    return work


def commit(work, files: dict[str, str | None], message: str) -> str:
    for name, text in files.items():
        path = work / name
        if text is None:
            git(work, "rm", "-q", name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode())
            git(work, "add", name)
    git(work, "commit", "-qm", message)
    git(work, "push", "-q", "origin", "main")
    return git(work, "rev-parse", "HEAD")


def loader(tmp_path, **kw):
    defaults = dict(
        location=URL,
        ref="main",
        include=("**/*.md",),
        exclude=(),
        repo_root=tmp_path,
        cache_root=tmp_path / "cache",
        provider="github",
    )
    return GitLoader(**{**defaults, **kw})


# --- provider formats -------------------------------------------------------------------------


def test_auth_headers_per_provider():
    basic = auth_header("github", "t").removeprefix("Authorization: Basic ")
    assert base64.b64decode(basic) == b"x-access-token:t"
    basic = auth_header("bitbucket-cloud", "t").removeprefix("Authorization: Basic ")
    assert base64.b64decode(basic) == b"x-token-auth:t"
    assert auth_header("bitbucket-dc", "t") == "Authorization: Bearer t"
    with pytest.raises(ValueError):
        auth_header("gitlab", "t")


@pytest.mark.parametrize(
    ("provider", "location", "expected"),
    [
        ("github", URL, "https://github.com/acme/repo/blob/abc/docs/a%20b.md"),
        (
            "github",  # GitHub Enterprise Server
            "https://git.example.com/acme/repo.git",
            "https://git.example.com/acme/repo/blob/abc/docs/a%20b.md",
        ),
        (
            "bitbucket-cloud",
            "https://bitbucket.org/ws/repo.git",
            "https://bitbucket.org/ws/repo/src/abc/docs/a%20b.md",
        ),
        (
            "bitbucket-dc",
            "https://bb.example.com/scm/pay/repo.git",
            "https://bb.example.com/projects/PAY/repos/repo/browse/docs/a%20b.md?at=abc",
        ),
        (
            "bitbucket-dc",  # behind a context path
            "https://example.com/bitbucket/scm/pay/repo.git",
            "https://example.com/bitbucket/projects/PAY/repos/repo/browse/docs/a%20b.md?at=abc",
        ),
        (None, ".", None),
    ],
)
def test_deep_links(provider, location, expected):
    assert deep_link(provider, location, "abc", "docs/a b.md") == expected


def test_auth_header_is_scoped_to_the_repository_host():
    env = remote_git_env(URL, "Authorization: Bearer x")
    keys = {env[f"GIT_CONFIG_KEY_{i}"]: env[f"GIT_CONFIG_VALUE_{i}"] for i in range(2)}
    assert keys == {
        "credential.helper": "",
        "http.https://github.com/.extraHeader": "Authorization: Bearer x",
    }
    assert env["GIT_CONFIG_COUNT"] == "2" and env["GIT_TERMINAL_PROMPT"] == "0"


# --- clone, branch tracking, incremental --------------------------------------------------------


def test_tracks_the_branch_and_reads_incrementally(upstream, tmp_path):
    c1 = commit(upstream, {"a.md": "# A1\n", "c.md": "# C\n", "x.txt": "not selected"}, "one")
    first = loader(tmp_path)
    items = {i.path: i for i in first.items()}
    assert set(items) == {"a.md", "c.md"} and not first.incremental
    assert items["a.md"].url == f"https://github.com/acme/repo/blob/{c1}/a.md"
    assert first.cursor["commit"] == c1

    c2 = commit(upstream, {"a.md": "# A2\n", "b.md": "# B\n", "c.md": None}, "two")
    second = loader(tmp_path)
    items = {i.path: i for i in second.items(first.cursor)}
    assert second.details == {"commit": c2, "mode": "incremental"} and second.incremental
    assert set(items) == {"a.md", "b.md"}  # changed only
    assert items["a.md"].text == "# A2\n" and c2 in items["a.md"].url
    assert second.all_ids() == {"a.md", "b.md"}  # c.md deleted upstream

    # unchanged commit: nothing to read, every id still listed
    third = loader(tmp_path)
    assert list(third.items(second.cursor)) == [] and third.all_ids() == {"a.md", "b.md"}


def test_changed_globs_or_location_mean_a_full_read(upstream, tmp_path):
    commit(upstream, {"a.md": "# A\n", "b.txt": "b"}, "one")
    first = loader(tmp_path)
    list(first.items())
    wider = loader(tmp_path, include=("**/*.md", "**/*.txt"))
    assert {i.path for i in wider.items(first.cursor)} == {"a.md", "b.txt"}
    assert not wider.incremental
    unknown = dict(first.cursor, commit="0" * 40)  # e.g. history rewritten
    again = loader(tmp_path)
    assert {i.path for i in again.items(unknown)} == {"a.md"} and not again.incremental


def test_pinned_sha(upstream, tmp_path):
    c1 = commit(upstream, {"a.md": "# A1\n"}, "one")
    commit(upstream, {"a.md": "# A2\n"}, "two")
    pinned = loader(tmp_path, ref=c1)
    [item] = list(pinned.items())
    assert item.text == "# A1\n" and pinned.details["commit"] == c1


def test_token_goes_to_the_git_environment_never_argv(upstream, tmp_path, monkeypatch):
    commit(upstream, {"a.md": "# A\n"}, "one")
    calls = []
    real_run = subprocess.run

    def spy(cmd, *args, **kwargs):
        calls.append((cmd, kwargs.get("env") or {}))
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    secrets = SecretResolver(EnvSecretStore({"SDLC_SECRET_GITHUB_TOKEN": TOKEN}), {})
    remote = loader(tmp_path, secrets=secrets, credentials=("secret", "github-token"))
    assert [i.path for i in remote.items()] == ["a.md"]
    network = [(cmd, env) for cmd, env in calls if "clone" in cmd or "fetch" in cmd]
    assert len(network) == 2
    expected = auth_header("github", TOKEN)
    for cmd, env in network:
        assert not any(TOKEN in arg or expected in arg for arg in cmd)
        assert expected in env.values()
    for cmd, env in calls:  # local reads never get the token
        if "clone" not in cmd and "fetch" not in cmd:
            assert expected not in (env or {}).values()


class CountingSecrets:
    def __init__(self):
        self.invalidated = 0

    def resolve(self, ref):
        from sdlc_secrets import SecretValue

        return SecretValue("t")

    def invalidate(self, ref):
        self.invalidated += 1


def test_failed_clone_drops_the_cached_secret(tmp_path, monkeypatch):
    gitconfig = tmp_path / "gitconfig"
    missing = (tmp_path / "missing.git").as_uri()
    gitconfig.write_text(f'[url "{missing}"]\n\tinsteadOf = {URL}\n')
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    secrets = CountingSecrets()
    remote = loader(tmp_path, secrets=secrets, credentials=("secret", "github-token"))
    with pytest.raises(LoaderError, match="clone failed"):
        list(remote.items())
    assert secrets.invalidated == 1


def test_missing_secret_is_a_loader_error(tmp_path):
    remote = loader(
        tmp_path,
        secrets=SecretResolver(EnvSecretStore({}), {}),
        credentials=("secret", "github-token"),
    )
    with pytest.raises(LoaderError, match="credentials secret:github-token"):
        list(remote.items())
