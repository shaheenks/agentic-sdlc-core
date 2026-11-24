"""One ingest run over the declared sources (FR-KNOW-001, FR-KNOW-003; DEC-0011).

Every run writes a complete store. Files whose content hash is unchanged keep their chunks and embeddings (and
their cached extraction) from the previous store; files that are gone are left out; the structural graph is
rebuilt each time, since it is cheap and links between files change. A source that cannot be read keeps its
previous records and is reported as failed."""

import asyncio
import dataclasses
import hashlib
import json
import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sdlc_knowledge import DOCUMENT, Chunk, Edge, Embedder, Entity, Store, StoreError, read_store, write_store

from knowledge_ingest.chunking import CHUNKER, chunk
from knowledge_ingest.extract import CachedExtraction, Extractor, concept_graph
from knowledge_ingest.fetch import Fetched, FetchError, fetch_folder, fetch_git, link_for
from knowledge_ingest.graph import file_graph, modules_of, source_entity_id

EXTRACTIONS = "extractions.jsonl"
EMBED_BATCH = 256
log = logging.getLogger("knowledge_ingest")


@dataclass
class Previous:
    store: Store = field(default_factory=Store)
    extractions: list[CachedExtraction] = field(default_factory=list)

    @classmethod
    def read(cls, directory: Path | None) -> "Previous":
        if directory is None or not (Path(directory) / "manifest.json").is_file():
            return cls()
        try:
            store = read_store(directory)
        except StoreError as exc:
            log.warning("previous store unreadable, starting afresh: %s", exc)
            return cls()
        extractions = []
        path = Path(directory) / EXTRACTIONS
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        extractions.append(CachedExtraction(**json.loads(line)))
                    except (TypeError, json.JSONDecodeError):
                        continue
        return cls(store, extractions)

    def of(self, source_id: str) -> tuple[list[Chunk], list[Entity], list[Edge], list[CachedExtraction]]:
        s = self.store
        return (
            [c for c in s.chunks if c.source_id == source_id],
            [e for e in s.entities if e.source_id == source_id],
            [e for e in s.edges if e.source_id == source_id],
            [x for x in self.extractions if x.source_id == source_id],
        )


@dataclass
class Result:
    store: Store
    extractions: list[CachedExtraction]
    failed: list[str]


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def _embed(embedder: Embedder, texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        vectors.extend(await embedder.embed(texts[i : i + EMBED_BATCH], DOCUMENT))
    return vectors


async def _ingest_source(
    sid: str,
    source: Mapping[str, Any],
    fetched: Fetched,
    previous: Previous,
    reuse_chunks: bool,
    embedder: Embedder,
    extractor: Extractor | None,
) -> tuple[Store, list[CachedExtraction], dict[str, Any]]:
    cls = source["classification"]
    old_chunks, _, _, old_extractions = previous.of(sid)
    by_file: dict[str, list[Chunk]] = {}
    if reuse_chunks:
        for c in old_chunks:
            by_file.setdefault(c.path, []).append(c)
    chunks: list[Chunk] = []
    pending: list[tuple[str, str, str, Any, str]] = []  # path, hash, link, piece, text to embed
    reused = 0
    hashes = {path: _hash(text) for path, text in fetched.files.items()}
    for path in sorted(fetched.files):
        h, link = hashes[path], link_for(source, path, fetched.revision)
        kept = by_file.get(path) or []
        if kept and all(c.file_hash == h for c in kept):
            chunks.extend(dataclasses.replace(c, classification=cls, link=link) for c in kept)
            reused += len(kept)
            continue
        for piece in chunk(path, fetched.files[path]):
            embed_text = f"{path}\n{piece.heading}\n\n{piece.text}" if piece.heading else f"{path}\n\n{piece.text}"
            pending.append((path, h, link, piece, embed_text))
    vectors = await _embed(embedder, [p[4] for p in pending])
    for (path, h, link, piece, _), vector in zip(pending, vectors, strict=True):
        chunks.append(
            Chunk(
                f"{sid}:{path}#L{piece.start_line}",
                sid,
                cls,
                path,
                link,
                piece.start_line,
                piece.end_line,
                piece.heading,
                piece.text,
                h,
                tuple(vector),
            )
        )
    chunks.sort(key=lambda c: (c.path, c.start_line))

    entities = [Entity(source_entity_id(sid), sid, cls, "source", source["name"], "", source.get("description", ""))]
    edges: list[Edge] = []
    paths, modules = set(fetched.files), modules_of(sorted(fetched.files))
    for path in sorted(fetched.files):
        g = file_graph(sid, cls, path, fetched.files[path], hashes[path], paths, modules)
        entities.extend(g.entities)
        edges.extend(g.edges)

    extractions: list[CachedExtraction] = []
    extracted = errors = 0
    if extractor is not None and source.get("extract", True):
        cache = {(x.path, x.file_hash): x for x in old_extractions if x.model == extractor.model}
        todo = [p for p in sorted(fetched.files) if (p, hashes[p]) not in cache]

        async def one(path: str):
            try:
                return path, await extractor.extract(path, fetched.files[path])
            except Exception as exc:  # one file's failure must not stop the run
                log.warning("extraction failed for %s/%s: %s", sid, path, type(exc).__name__)
                return path, None

        for path, found in await asyncio.gather(*(one(p) for p in todo)):
            if found is None:
                errors += 1
            else:
                extracted += 1
                cache[(path, hashes[path])] = CachedExtraction(sid, cls, path, hashes[path], extractor.model, found)
        extractions = [
            dataclasses.replace(cache[(p, hashes[p])], classification=cls)
            for p in sorted(fetched.files)
            if (p, hashes[p]) in cache
        ]
        concepts = concept_graph(sid, cls, {x.path: (x.file_hash, x.result) for x in extractions})
        entities.extend(concepts.entities)
        edges.extend(concepts.edges)
    else:
        extractions = [x for x in old_extractions if hashes.get(x.path) == x.file_hash]

    status = {
        "status": "ok",
        "kind": source["kind"],
        "location": source["location"],
        "revision": fetched.revision,
        "files": len(fetched.files),
        "skipped": fetched.skipped,
        "chunks": len(chunks),
        "embedded": len(pending),
        "reused": reused,
        "entities": len(entities),
        "edges": len(edges),
        "extracted": extracted,
        "extraction_errors": errors,
    }
    return Store({}, chunks, entities, edges), extractions, status


def _fetch(source: Mapping[str, Any], root: Path, read_secret: Callable[[str], str], gcs_client=None) -> Fetched:
    if source["kind"] == "git":
        return fetch_git(source, read_secret)
    return fetch_folder(source, root, gcs_client)


async def ingest(
    sources: Mapping[str, Mapping[str, Any]],
    *,
    root: Path,
    previous: Previous,
    embedder: Embedder,
    extractor: Extractor | None,
    read_secret: Callable[[str], str],
    only: set[str] | None = None,
    context: Mapping[str, Any] | None = None,
    gcs_client=None,
) -> Result:
    started = datetime.now(UTC)
    old = previous.store.manifest
    reuse_chunks = (
        old.get("embedding") == {"model": embedder.model, "dimensions": embedder.dimensions}
        and old.get("chunker") == CHUNKER
    )
    store, extractions, failed = Store(), [], []
    statuses: dict[str, Any] = {}
    for sid in sorted(sources):
        source = sources[sid]
        carried = previous.of(sid)
        if only is not None and sid not in only:
            if (old.get("sources") or {}).get(sid):
                statuses[sid] = old["sources"][sid]
                _add(store, extractions, carried)
            continue
        try:
            fetched = await asyncio.to_thread(_fetch, source, root, read_secret, gcs_client)
            part, found, status = await _ingest_source(
                sid, source, fetched, previous, reuse_chunks, embedder, extractor
            )
        except (FetchError, OSError) as exc:
            log.error("source %s failed: %s", sid, exc)
            failed.append(sid)
            before = (old.get("sources") or {}).get(sid) or {}
            statuses[sid] = {**before, "status": "failed", "error": str(exc)[:300], "kind": source["kind"]}
            if reuse_chunks:
                _add(store, extractions, carried)
            continue
        log.info("source %s: %s", sid, json.dumps(status))
        statuses[sid] = status
        _add(store, extractions, (part.chunks, part.entities, part.edges, found))
    store.manifest = {
        **(context or {}),
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "embedding": {"model": embedder.model, "dimensions": embedder.dimensions},
        "chunker": CHUNKER,
        "extraction": {"model": extractor.model} if extractor else None,
        "sources": statuses,
    }
    return Result(store, extractions, failed)


def _add(store: Store, extractions: list[CachedExtraction], part) -> None:
    chunks, entities, edges, found = part
    store.chunks.extend(chunks)
    store.entities.extend(entities)
    store.edges.extend(edges)
    extractions.extend(found)


def write(directory: Path, result: Result) -> None:
    write_store(directory, result.store)
    tmp = Path(directory) / (EXTRACTIONS + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        for x in result.extractions:
            f.write(json.dumps(asdict(x), ensure_ascii=False, separators=(",", ":")) + "\n")
    os.replace(tmp, Path(directory) / EXTRACTIONS)
