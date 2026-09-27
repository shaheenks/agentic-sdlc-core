"""Ingest one or all sources: sync registry -> walk -> chunk -> embed -> replace changed docs.

Runs as the sdlc_ingest DB role (its RLS policy sees every row). Unchanged files (same content
hash) are skipped; files that disappeared are deleted. Classification comes from the Source
config and is stamped on every document and chunk (RLS filters on it).
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from psycopg import AsyncConnection
from sdlc_config import Snapshot
from sdlc_db.embedding import Embedder
from sdlc_db.knowledge import (
    ChunkRow,
    delete_documents,
    document_hashes,
    replace_document,
    sync_sources,
)

from sdlc_ingest.chunker import chunk_text
from sdlc_ingest.files import resolve_location, walk

log = logging.getLogger("sdlc.ingest")


@dataclass
class SourceReport:
    source_id: str
    files_seen: int = 0
    files_changed: int = 0
    files_unchanged: int = 0
    files_deleted: int = 0
    chunks_written: int = 0
    errors: list[str] = field(default_factory=list)


async def ingest(
    conn: AsyncConnection,
    snapshot: Snapshot,
    embedder: Embedder,
    repo_root: Path,
    source_ids: list[str] | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> list[SourceReport]:
    if embedder.dimensions != snapshot.platform.embedding_dimensions:
        raise ValueError("embedder dimensions do not match platform.yaml knowledge.embedding")
    if not dry_run:
        count, removed = await sync_sources(conn, snapshot)
        log.info("source registry synced: %d sources, removed %s", count, removed or "none")
    wanted = source_ids or sorted(snapshot.sources)
    reports = []
    for source_id in wanted:
        if source_id not in snapshot.sources:
            raise ValueError(f"unknown source '{source_id}' (have: {sorted(snapshot.sources)})")
        reports.append(
            await _ingest_source(conn, snapshot, embedder, repo_root, source_id, dry_run, force)
        )
    return reports


async def _ingest_source(conn, snapshot, embedder, repo_root, source_id, dry_run, force=False):
    source = snapshot.sources[source_id]
    report = SourceReport(source_id)
    folder = resolve_location(source.location, repo_root)
    known = {} if dry_run else await document_hashes(conn, source_id)
    chunking = dict(source.chunking)
    seen = set()
    for file in walk(folder, source.include, source.exclude):
        report.files_seen += 1
        seen.add(file.path)
        if not force and known.get(file.path) == file.content_hash:
            report.files_unchanged += 1
            continue
        chunks = chunk_text(
            file.path,
            file.text,
            chunking.get("strategy", "auto"),
            chunking.get("max_tokens", 400),
            chunking.get("overlap", 40),
        )
        report.files_changed += 1
        report.chunks_written += len(chunks)
        if dry_run or not chunks:
            continue
        # the file path is prepended so paths and headings are searchable too
        texts = [f"{file.path}\n{c.heading or ''}\n{c.content}" for c in chunks]
        vectors = embedder.embed(texts, kind="document")
        rows = [
            ChunkRow(c.ordinal, c.start_line, c.end_line, c.heading, c.content, v)
            for c, v in zip(chunks, vectors, strict=True)
        ]
        await replace_document(
            conn,
            source_id,
            source.classification_rank,
            file.path,
            file.content_hash,
            rows,
            embedder.model,
        )
    gone = sorted(set(known) - seen)
    if gone and not dry_run:
        report.files_deleted = await delete_documents(conn, source_id, gone)
    log.info("ingested %s: %s", source_id, report)
    return report
