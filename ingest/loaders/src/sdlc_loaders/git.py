"""git sources (version-01 M1): local repositories and remote ones on GitHub, Bitbucket Cloud and
Bitbucket Data Center.

- `ref` is a full SHA (pinned) or a branch/tag (tracked: resolved on every run). Remote repositories
  are read at the commit the fetch resolved (FETCH_HEAD), so a tracked branch is always current.
- Incremental: the cursor stores the commit (plus the location and a hash of include/exclude). The
  next run reads only paths changed since that commit (`git diff`) and lists every current path for
  deletions. A missing old commit, a new location or changed globs mean a full read.
- Credentials (`spec.credentials`) are resolved per run through sdlc_secrets and sent as an HTTP
  header to the repository host only, in the git process environment (never argv or the URL). An
  authentication failure drops the cached secret so the next run re-reads it.
- Each item links to the file at its commit (`url`), in the provider's format.
"""

import base64
import hashlib
import json
from collections.abc import Iterator, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from sdlc_loaders.base import Loader, LoaderError, SourceItem
from sdlc_loaders.files import (
    FETCHED,
    GitSourceError,
    changed_paths,
    git_repository,
    read_blobs,
    resolve_commit,
    selected_paths,
)

PROVIDERS = ("github", "bitbucket-cloud", "bitbucket-dc")


def auth_header(provider: str, token: str) -> str:
    """The HTTP header git sends for a read-only token, per provider:
    GitHub (App installation token or fine-grained PAT) and Bitbucket Cloud (repository access
    token) use Basic auth with a fixed user name; Bitbucket DC HTTP access tokens are Bearer."""
    if provider == "github":
        return (
            "Authorization: Basic " + base64.b64encode(f"x-access-token:{token}".encode()).decode()
        )
    if provider == "bitbucket-cloud":
        return "Authorization: Basic " + base64.b64encode(f"x-token-auth:{token}".encode()).decode()
    if provider == "bitbucket-dc":
        return f"Authorization: Bearer {token}"
    raise ValueError(f"unknown git provider '{provider}'")


def repo_web_parts(provider: str, location: str) -> tuple[str, list[str]]:
    """(https://host, path segments without .git) of a remote repository URL."""
    parts = urlsplit(location)
    segments = [s for s in parts.path.split("/") if s]
    if segments and segments[-1].endswith(".git"):
        segments[-1] = segments[-1][:-4]
    return f"https://{parts.netloc}", segments


def deep_link(provider: str | None, location: str, commit: str, path: str) -> str | None:
    """Link to `path` at `commit` in the provider's web UI; None for local repositories."""
    if not provider or not location.startswith("https://"):
        return None
    base, segments = repo_web_parts(provider, location)
    quoted = quote(path, safe="/")
    if provider == "github" and len(segments) >= 2:
        return f"{base}/{segments[-2]}/{segments[-1]}/blob/{commit}/{quoted}"
    if provider == "bitbucket-cloud" and len(segments) >= 2:
        return f"{base}/{segments[-2]}/{segments[-1]}/src/{commit}/{quoted}"
    if provider == "bitbucket-dc" and len(segments) >= 3 and segments[-3] == "scm":
        prefix = "/".join(segments[:-3])  # DC behind a context path, e.g. /bitbucket
        root = f"{base}/{prefix}" if prefix else base
        project, repo = segments[-2], segments[-1]
        return f"{root}/projects/{project.upper()}/repos/{repo}/browse/{quoted}?at={commit}"
    return None


def _selection(include: tuple[str, ...], exclude: tuple[str, ...]) -> str:
    return hashlib.sha256(json.dumps([include, exclude]).encode()).hexdigest()[:16]


class GitLoader(Loader):
    def __init__(
        self,
        location: str,
        ref: str,
        include: tuple[str, ...],
        exclude: tuple[str, ...],
        repo_root: Path,
        cache_root: Path,
        provider: str | None = None,
        secrets=None,
        credentials: tuple[str, str] | None = None,
    ) -> None:
        super().__init__()
        self.location, self.ref, self.provider = location, ref, provider
        self.include, self.exclude = include, exclude
        self.repo_root, self.cache_root = repo_root, cache_root
        self._secrets, self._credentials = secrets, credentials
        self._ids: set[str] = set()

    @property
    def remote(self) -> bool:
        return self.location.startswith("https://")

    def _auth_header(self) -> str | None:
        if not self._credentials:
            return None
        if self._secrets is None:
            raise LoaderError("source names credentials but no secret resolver was given")
        try:
            token = self._secrets.resolve(self._credentials)
        except Exception as e:  # SecretError: name only, never a value
            kind, name = self._credentials
            raise LoaderError(f"credentials {kind}:{name}: {e}") from None
        return auth_header(self.provider, token.reveal())

    def items(self, cursor: Mapping[str, Any] | None = None) -> Iterator[SourceItem]:
        try:
            repo = git_repository(
                self.location, self.repo_root, self.cache_root, self.ref, self._auth_header()
            )
            commit = resolve_commit(repo, FETCHED if self.remote else self.ref)
            wanted = selected_paths(repo, commit, self.include, self.exclude)
        except GitSourceError as e:
            if self._credentials and self._secrets is not None:
                self._secrets.invalidate(self._credentials)  # maybe rotated: re-read next run
            raise LoaderError(str(e)) from e
        selection = _selection(self.include, self.exclude)
        self._ids = set(wanted)
        changed = None
        if (
            cursor
            and cursor.get("location") == self.location
            and cursor.get("selection") == selection
            and cursor.get("commit")
        ):
            try:
                changed = changed_paths(repo, cursor["commit"], commit)
            except GitSourceError:
                changed = None
        self.incremental = changed is not None
        paths = [p for p in wanted if p in changed] if changed is not None else wanted
        self.details.update(commit=commit, mode="incremental" if self.incremental else "full")
        try:
            for item in read_blobs(repo, commit, paths):
                yield replace(item, url=deep_link(self.provider, self.location, commit, item.path))
        except GitSourceError as e:
            raise LoaderError(str(e)) from e
        self.cursor = {"commit": commit, "location": self.location, "selection": selection}

    def all_ids(self) -> set[str]:
        return set(self._ids)


def git(source, repo_root: Path, cache_root: Path, secrets=None) -> Loader:
    return GitLoader(
        source.location,
        source.ref,
        source.include,
        source.exclude,
        repo_root,
        cache_root / "git",
        provider=source.provider,
        secrets=secrets,
        credentials=source.credentials,
    )
