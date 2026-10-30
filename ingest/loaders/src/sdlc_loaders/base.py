"""The loader contract (version-01 M0): every source type yields `SourceItem`s.

A loader reads one source and yields its items. The pipeline (sdlc_ingest) chunks, embeds and writes
them; it never talks to a source system itself.

  items(cursor)  the items to (re)consider. Full loaders (local_folder, git) yield every item and
                 ignore the cursor; incremental loaders yield items changed since the cursor.
  all_ids()      incremental loaders only: the ids of every item that still exists (a cheap
                 id-only listing), so the pipeline can delete what disappeared.
  cursor         after `items()` is exhausted: the state to store in sync_state for the next run
                 (None = nothing to store). It is saved only when the run had no errors.
  details        facts for the run report (e.g. the resolved git commit).
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sdlc_connectors.errors import ConnectorError

PDF = "application/pdf"
TEXT = "text/plain"
MARKDOWN = "text/markdown"


@dataclass(frozen=True)
class SourceItem:
    path: str  # stable item id: a file path, `PAY/123456` (page), `PAY-123` (issue)
    text: str  # "" for PDFs (their text comes from sdlc_ingest.pdf)
    content_hash: str
    media_type: str = TEXT  # text/plain, text/markdown or application/pdf
    raw: bytes | None = None  # PDFs only
    title: str | None = None  # shown in citations
    url: str | None = None  # deep link for citations (https only)
    updated_at: datetime | None = None
    # Natively restricted in the source system (page/issue restrictions): never ingested, and a
    # stored copy is deleted (version-01 §2.6).
    restricted: bool = False

    @property
    def is_pdf(self) -> bool:
        return self.media_type == PDF


@dataclass(frozen=True)
class LoaderContext:
    """What a loader factory gets besides its Source."""

    repo_root: Path  # local locations resolve against it
    cache_root: Path  # writable cache (git clones)
    secrets: Any = None  # sdlc_secrets.SecretResolver, for spec.credentials
    allowed_hosts: tuple[str, ...] = ()  # platform.yaml knowledge.allowed_hosts


# A source cannot be read at all (missing folder, unreachable host, bad credentials). The same
# class as sdlc_connectors' errors, so HTTP failures (HttpError) are loader errors too.
LoaderError = ConnectorError


class Loader(ABC):
    incremental: bool = False

    def __init__(self) -> None:
        self.cursor: dict[str, Any] | None = None
        self.details: dict[str, Any] = {}

    @abstractmethod
    def items(self, cursor: Mapping[str, Any] | None = None) -> Iterator[SourceItem]: ...

    def all_ids(self) -> set[str]:
        raise NotImplementedError(f"{type(self).__name__} is not incremental")
