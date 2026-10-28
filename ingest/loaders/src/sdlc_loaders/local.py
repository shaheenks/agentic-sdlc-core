"""Loaders for the version-00 source types, unchanged in behaviour: full scans, no cursor needed
(unchanged files are skipped by content hash in the pipeline)."""

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from sdlc_loaders.base import Loader, LoaderError, SourceItem
from sdlc_loaders.files import GitSourceError, git_repository, resolve_location, walk, walk_git


class LocalFolderLoader(Loader):
    """Files under a folder (working tree)."""

    def __init__(self, folder: Path, include: tuple[str, ...], exclude: tuple[str, ...]) -> None:
        super().__init__()
        self.folder, self.include, self.exclude = folder, include, exclude

    def items(self, cursor: Mapping[str, Any] | None = None) -> Iterator[SourceItem]:
        try:
            yield from walk(self.folder, self.include, self.exclude)
        except FileNotFoundError as e:
            raise LoaderError(str(e)) from e


class GitLoader(Loader):
    """Files of one commit (`ref`) in a local repository or an https URL; never the working tree.
    The resolved commit is reported (details["commit"]) and stored as the cursor."""

    def __init__(
        self,
        location: str,
        ref: str,
        include: tuple[str, ...],
        exclude: tuple[str, ...],
        repo_root: Path,
        cache_root: Path,
    ) -> None:
        super().__init__()
        self.location, self.ref = location, ref
        self.include, self.exclude = include, exclude
        self.repo_root, self.cache_root = repo_root, cache_root

    def items(self, cursor: Mapping[str, Any] | None = None) -> Iterator[SourceItem]:
        try:
            repo = git_repository(self.location, self.repo_root, self.cache_root, self.ref)
            commit, files = walk_git(repo, self.ref, self.include, self.exclude)
        except GitSourceError as e:
            raise LoaderError(str(e)) from e
        self.details["commit"] = commit
        yield from files
        self.cursor = {"commit": commit}


def local_folder(source, repo_root: Path, cache_root: Path, secrets=None) -> Loader:
    return LocalFolderLoader(
        resolve_location(source.location, repo_root), source.include, source.exclude
    )


def git(source, repo_root: Path, cache_root: Path, secrets=None) -> Loader:
    return GitLoader(
        source.location,
        source.ref,
        source.include,
        source.exclude,
        repo_root,
        cache_root / "git",
    )
