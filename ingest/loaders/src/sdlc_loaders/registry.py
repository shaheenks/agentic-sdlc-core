"""Source type -> loader factory. A new source type registers its factory here (and its `spec`
block in config/schemas/source.schema.json)."""

from collections.abc import Callable
from pathlib import Path

from sdlc_config.model import SourceDef
from sdlc_secrets import SecretResolver

from sdlc_loaders import gcs, git, local
from sdlc_loaders.base import Loader, LoaderError

# factory(source, repo_root, cache_root, secrets) -> Loader
LoaderFactory = Callable[[SourceDef, Path, Path, SecretResolver | None], Loader]

LOADERS: dict[str, LoaderFactory] = {
    "local_folder": local.local_folder,
    "git": git.git,
    "gcs": gcs.gcs,
}


def make_loader(
    source: SourceDef,
    repo_root: Path,
    cache_root: Path | None = None,
    secrets: SecretResolver | None = None,
) -> Loader:
    factory = LOADERS.get(source.type)
    if factory is None:
        raise LoaderError(f"no loader for source type '{source.type}'")
    return factory(source, repo_root, cache_root or repo_root / ".cache", secrets)
