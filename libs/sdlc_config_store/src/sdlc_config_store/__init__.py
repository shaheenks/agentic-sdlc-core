"""Versioned configuration bundles and the store services read them from (FR-CFG-001, FR-CFG-003, FR-CFG-005).

Layout of a bundle location (a folder locally, the configuration bucket on Google Cloud):

    bundles/<version>.json      one compiled bundle; never changes once written
    active.json                 names the active version; activation rewrites only this object
    activations/<time>.json     one record per activation: who activated which version, and when

A bundle's version is a hash of its environment and content, so a bundle whose content does not match its
version is refused. Services read `active.json` at most every `refresh_seconds`, compare its generation
with the last one they saw, and load a new bundle only when it changed. A newly activated version takes
effect within that interval, without a restart. With no verified bundle, every request is refused.
"""

from sdlc_config_store.bundle import (
    Bundle,
    ConfigUnavailable,
    content_version,
    make_bundle,
    make_pointer,
    parse_bundle,
    parse_pointer,
)
from sdlc_config_store.sources import DirSource, GcsSource, Source, source_from_url
from sdlc_config_store.store import ConfigStore

__all__ = [
    "Bundle",
    "ConfigStore",
    "ConfigUnavailable",
    "DirSource",
    "GcsSource",
    "Source",
    "content_version",
    "make_bundle",
    "make_pointer",
    "parse_bundle",
    "parse_pointer",
    "source_from_url",
]
