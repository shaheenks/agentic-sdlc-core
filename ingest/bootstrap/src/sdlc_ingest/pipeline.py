"""Ingest one or all sources: sync registry -> walk -> chunk -> embed -> extract graph ->
replace changed docs.

Runs as the sdlc_ingest DB role (its RLS policy sees every row). Unchanged files (same content
hash) are skipped; files that disappeared are deleted. Classification comes from the Source
config and is stamped on every document, chunk and graph row (RLS filters on it).
Graph extraction runs for sources with spec.ingest.graph.enabled when an extractor is given; a
document whose extraction fails is not written, so the next run retries it.
PDFs (H10) are read page by page (sdlc_ingest.pdf: text layer, model OCR for text-less pages only
when the source sets pdf.ocr: gemini and an OCR reader is given) and chunked by pages
(chunk_pdf); oversized, encrypted or corrupt PDFs are reported and not written.
Items come from the source's loader (sdlc_loaders, version-01 M0). Natively restricted items are
never written (a stored copy is deleted); a changed title/URL with unchanged content updates the
metadata only. Incremental loaders resume from their sync_state cursor and report every existing
id (all_ids) so deletions are still found; the cursor is saved only after a run without errors.
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
    get_sync_cursor,
    replace_document,
    set_sync_cursor,
    stored_documents,
    sync_sources,
    update_document_metadata,
)
from sdlc_loaders import LoaderError, make_loader
from sdlc_secrets import SecretResolver

from sdlc_ingest.chunker import chunk_pdf, chunk_text
from sdlc_ingest.extract import Extractor, extract_chunks
from sdlc_ingest.pdf import OcrReader, PdfError, read_pdf

log = logging.getLogger("sdlc.ingest")


@dataclass
class SourceReport:
    source_id: str
    files_seen: int = 0
    files_changed: int = 0
    files_unchanged: int = 0
    files_deleted: int = 0
    files_restricted: int = 0  # natively restricted items skipped (version-01 §2.6)
    metadata_updated: int = 0  # title/url refreshed without re-embedding
    chunks_written: int = 0
    entities_written: int = 0
    relations_written: int = 0
    extraction_calls: int = 0  # model calls (cache misses)
    commit: str | None = None  # git sources: the resolved commit that was ingested
    mode: str = "full"  # "incremental": only items changed since the stored cursor were read
    pdf_pages: int = 0  # pages read from changed PDFs
    pdf_pages_without_text: int = 0  # text-less pages not read by a model (pdf.ocr: none)
    ocr_calls: int = 0  # model calls for text-less PDF pages (cache misses)
    errors: list[str] = field(default_factory=list)


async def ingest(
    conn: AsyncConnection,
    snapshot: Snapshot,
    embedder: Embedder,
    repo_root: Path,
    source_ids: list[str] | None = None,
    dry_run: bool = False,
    force: bool = False,
    extractor: Extractor | None = None,
    ocr: OcrReader | None = None,
    secrets: SecretResolver | None = None,
    cache_root: Path | None = None,
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
            await _ingest_source(
                conn,
                snapshot,
                embedder,
                repo_root,
                source_id,
                dry_run,
                force,
                extractor,
                ocr,
                secrets,
                cache_root,
            )
        )
    return reports


async def _ingest_source(
    conn,
    snapshot,
    embedder,
    repo_root,
    source_id,
    dry_run,
    force=False,
    extractor=None,
    ocr=None,
    secrets=None,
    cache_root=None,
):
    source = snapshot.sources[source_id]
    report = SourceReport(source_id)
    loader = make_loader(source, repo_root, cache_root, secrets, snapshot.platform.allowed_hosts)
    # --force re-reads everything, so incremental loaders start from scratch too
    cursor = None if (dry_run or force) else await get_sync_cursor(conn, source_id)
    known = {} if dry_run else await stored_documents(conn, source_id)
    chunking = dict(source.chunking)
    seen, restricted = set(), set()
    pending = []  # (file, chunks) to (re)write
    files = loader.items(cursor)  # lazy: large sources are not held in memory
    while True:
        try:
            file = next(files)
        except StopIteration:
            break
        except LoaderError as e:  # nothing is written or deleted when a source cannot be read
            report.errors.append(str(e)[:500])
            log.warning("source %s not readable: %s", source_id, e)
            return report
        report.files_seen += 1
        if file.restricted:  # never ingested; a stored copy is deleted below
            report.files_restricted += 1
            restricted.add(file.path)
            continue
        seen.add(file.path)
        stored = known.get(file.path)
        if not force and stored is not None and stored.content_hash == file.content_hash:
            report.files_unchanged += 1
            if (stored.title, stored.url) != (file.title, file.url) and not dry_run:
                await update_document_metadata(conn, source_id, file.path, file.title, file.url)
                report.metadata_updated += 1
            continue
        if file.is_pdf:
            if len(file.raw) > source.pdf_max_mb * 1024 * 1024:
                report.errors.append(f"{file.path}: PDF larger than max_mb {source.pdf_max_mb}")
                continue
            use_ocr = ocr if (source.pdf_ocr == "gemini" and not dry_run) else None
            try:
                document = await read_pdf(
                    None if dry_run else conn,
                    file.raw,
                    max_pages=source.pdf_max_pages,
                    ocr=use_ocr,
                )
            except PdfError as e:  # reported, not written: retried next run
                report.errors.append(f"{file.path}: {e}"[:500])
                log.warning("PDF skipped %s/%s: %s", source_id, file.path, e)
                continue
            report.pdf_pages += len(document.pages)
            report.pdf_pages_without_text += document.pages_without_text
            report.ocr_calls += document.ocr_calls
            chunks = chunk_pdf(
                document, chunking.get("max_tokens", 400), chunking.get("overlap", 40)
            )
        else:
            strategy = chunking.get("strategy", "auto")
            if strategy == "auto" and file.media_type == "text/markdown":
                strategy = "markdown"  # converted pages/issues have no file extension
            chunks = chunk_text(
                file.path,
                file.text,
                strategy,
                chunking.get("max_tokens", 400),
                chunking.get("overlap", 40),
            )
        report.files_changed += 1
        if dry_run:
            report.chunks_written += len(chunks)
            continue
        # A file without text (empty, or a scan with OCR off) is still recorded, with no chunks,
        # so its hash is stored and it is not re-read every run (`--force` re-reads it, e.g.
        # after turning OCR on).
        pending.append((file, chunks))

    report.commit = loader.details.get("commit")
    report.mode = loader.details.get("mode", "full")

    # Model calls for all changed chunks of the source run as one parallel batch.
    graphs: dict[str, list] = {}
    if pending and source.graph_enabled and extractor is not None:
        items = [
            (f"{source_id}:{f.path}" + (f" p.{c.start_line}" if f.is_pdf else ""), c.content)
            for f, chunks in pending
            for c in chunks
        ]
        results, report.extraction_calls = await extract_chunks(conn, extractor, source, items)
        position = 0
        for f, chunks in pending:
            mine = results[position : position + len(chunks)]
            position += len(chunks)
            failed = next((r for r in mine if isinstance(r, Exception)), None)
            if failed is not None:  # not written, so the next run retries this file
                report.errors.append(f"{f.path}: graph extraction failed: {failed}"[:500])
                log.warning("graph extraction failed for %s/%s: %s", source_id, f.path, failed)
            else:
                graphs[f.path] = mine
        pending = [(f, chunks) for f, chunks in pending if f.path in graphs]

    # the file path is prepended so paths and headings are searchable too
    texts = [f"{f.path}\n{c.heading or ''}\n{c.content}" for f, chunks in pending for c in chunks]
    vectors = embedder.embed(texts, kind="document") if texts else []
    position = 0
    for file, chunks in pending:
        rows = [
            ChunkRow(c.ordinal, c.start_line, c.end_line, c.heading, c.content, v)
            for c, v in zip(chunks, vectors[position : position + len(chunks)], strict=True)
        ]
        position += len(chunks)
        counts = await replace_document(
            conn,
            source_id,
            source.classification_rank,
            file.path,
            file.content_hash,
            rows,
            embedder.model,
            graphs.get(file.path),
            file.media_type,
            file.title,
            file.url,
        )
        report.chunks_written += len(chunks)
        if counts is not None:
            report.entities_written += counts.entities
            report.relations_written += counts.relations
    if loader.incremental:  # changed items only were yielded: ask for every id that still exists
        try:
            existing = loader.all_ids() - restricted
        except LoaderError as e:  # without a full listing nothing is deleted this run
            report.errors.append(f"listing ids failed: {e}"[:500])
            existing = set(known)
    else:
        existing = seen
    gone = sorted(set(known) - existing)
    if gone and not dry_run:
        report.files_deleted = await delete_documents(conn, source_id, gone)
    if not dry_run and not report.errors:  # a failed item is retried: keep the old cursor
        await set_sync_cursor(conn, source_id, loader.cursor)
    log.info("ingested %s: %s", source_id, report)
    return report
