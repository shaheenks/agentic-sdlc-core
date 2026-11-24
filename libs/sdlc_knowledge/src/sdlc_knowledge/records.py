"""The knowledge store's records and their JSONL files (Knowledge Store; DEC-0011).

Every record carries `source_id` and `classification`; `read_store` refuses a file with a record that lacks
either, so untagged data can never be served."""

import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

CHUNKS, ENTITIES, EDGES, MANIFEST = "chunks.jsonl", "entities.jsonl", "edges.jsonl", "manifest.json"
FORMAT = 1


class StoreError(Exception):
    """The store's files are missing or malformed."""


@dataclass(frozen=True)
class Chunk:
    id: str
    source_id: str
    classification: str
    path: str  # the file's path inside its source
    link: str  # where a person can open the original
    start_line: int
    end_line: int
    heading: str
    text: str
    file_hash: str
    embedding: tuple[float, ...] = ()


@dataclass(frozen=True)
class Entity:
    id: str  # unique in the store; starts with the source ID
    source_id: str
    classification: str
    kind: str  # source, file, section, symbol, concept
    name: str
    path: str = ""
    description: str = ""
    file_hash: str = ""


@dataclass(frozen=True)
class Edge:
    source_id: str
    classification: str
    from_id: str
    to_id: str
    kind: str  # contains, links_to, imports, mentions, or a relation Gemini extracted
    file_hash: str = ""


@dataclass
class Store:
    manifest: dict[str, Any] = field(default_factory=dict)
    chunks: list[Chunk] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)


def _tagged(record: Mapping[str, Any], name: str, line: int) -> None:
    for key in ("source_id", "classification"):
        if not isinstance(record.get(key), str) or not record[key]:
            raise StoreError(f"{name}:{line}: record without {key}")


def _read(path: Path, kind: type) -> list:
    records = []
    if not path.is_file():
        raise StoreError(f"{path.name} is missing")
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise StoreError(f"{path.name}:{n}: {exc}") from exc
            _tagged(raw, path.name, n)
            if "embedding" in raw:
                raw["embedding"] = tuple(raw["embedding"])
            try:
                records.append(kind(**raw))
            except TypeError as exc:
                raise StoreError(f"{path.name}:{n}: {exc}") from exc
    return records


def read_store(directory: Path) -> Store:
    directory = Path(directory)
    try:
        manifest = json.loads((directory / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StoreError(f"{MANIFEST}: {exc}") from exc
    if manifest.get("format") != FORMAT:
        raise StoreError(f"{MANIFEST}: format {manifest.get('format')!r}, expected {FORMAT}")
    return Store(
        manifest,
        _read(directory / CHUNKS, Chunk),
        _read(directory / ENTITIES, Entity),
        _read(directory / EDGES, Edge),
    )


def _write_lines(path: Path, records: Iterable[Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            raw = asdict(record)
            _tagged(raw, path.name, 0)
            if "embedding" in raw:
                raw["embedding"] = [round(v, 7) for v in raw["embedding"]]
            f.write(json.dumps(raw, ensure_ascii=False, separators=(",", ":")) + "\n")
    os.replace(tmp, path)


def write_store(directory: Path, store: Store) -> None:
    """Writes every file, each replaced in one step; the manifest last, so a reader never sees a new manifest
    over old records."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    _write_lines(directory / CHUNKS, store.chunks)
    _write_lines(directory / ENTITIES, store.entities)
    _write_lines(directory / EDGES, store.edges)
    tmp = directory / (MANIFEST + ".tmp")
    tmp.write_text(json.dumps({**store.manifest, "format": FORMAT}, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, directory / MANIFEST)
