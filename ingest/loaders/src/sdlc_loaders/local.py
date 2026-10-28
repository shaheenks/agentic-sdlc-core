"""local_folder: files under a folder (working tree). Full scans, no cursor (unchanged files are
skipped by content hash in the pipeline). git sources: sdlc_loaders.git."""

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from sdlc_loaders.base import Loader, LoaderError, SourceItem
from sdlc_loaders.files import resolve_location, walk


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


def local_folder(source, repo_root: Path, cache_root: Path, secrets=None) -> Loader:
    return LocalFolderLoader(
        resolve_location(source.location, repo_root), source.include, source.exclude
    )
