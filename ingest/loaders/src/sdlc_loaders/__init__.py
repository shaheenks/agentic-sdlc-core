"""Source loaders (version-01 M0). See ingest/loaders/README.md."""

from sdlc_loaders.base import MARKDOWN, PDF, TEXT, Loader, LoaderError, SourceItem
from sdlc_loaders.registry import LOADERS, make_loader

__all__ = [
    "LOADERS",
    "MARKDOWN",
    "PDF",
    "TEXT",
    "Loader",
    "LoaderError",
    "SourceItem",
    "make_loader",
]
