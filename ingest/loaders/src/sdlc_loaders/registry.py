"""Source type -> loader factory. A new source type registers its factory here (and its `spec`
block in config/schemas/source.schema.json)."""

from collections.abc import Callable, Iterable
from pathlib import Path

from sdlc_config.model import SourceDef
from sdlc_secrets import SecretResolver

from sdlc_loaders import confluence, gcs, git, local
from sdlc_loaders.base import Loader, LoaderContext, LoaderError

LoaderFactory = Callable[[SourceDef, LoaderContext], Loader]

LOADERS: dict[str, LoaderFactory] = {
    "local_folder": local.local_folder,
    "git": git.git,
    "gcs": gcs.gcs,
    "confluence": confluence.confluence,
}


def make_loader(
    source: SourceDef,
    repo_root: Path,
    cache_root: Path | None = None,
    secrets: SecretResolver | None = None,
    allowed_hosts: Iterable[str] = (),
) -> Loader:
    factory = LOADERS.get(source.type)
    if factory is None:
        raise LoaderError(f"no loader for source type '{source.type}'")
    context = LoaderContext(
        repo_root, cache_root or repo_root / ".cache", secrets, tuple(allowed_hosts)
    )
    return factory(source, context)
