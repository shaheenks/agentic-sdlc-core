"""Concepts and their relations, extracted from each file by Gemini on Vertex AI (DEC-0011).

The model's answer for a file is cached with the file's content hash, so an unchanged file is not sent again.
Concept entities are merged per source by name: `<source>:concept:<slug>`; a file `mentions` its concepts."""

import asyncio
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from sdlc_knowledge import Edge, Entity

from knowledge_ingest.graph import Graph, file_entity_id, slug

MAX_CHARS = 30000
MAX_CONCEPTS = 20
MENTIONS = "mentions"
PROMPT = """You build a knowledge graph of a software organisation's systems and processes.
From the file below, list the main domain concepts it defines or relies on: systems, components, services,
requirements, decisions, data sets, processes, roles. Skip programming-language syntax, generic words and
library names. Give at most {max} concepts, each with a short type and a one-sentence description, and the
relations between them that the file states (for example: depends_on, implements, owns, calls, stores, part_of).

File: {path}
---
{text}
---"""
SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "concepts": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "type": {"type": "STRING"},
                    "description": {"type": "STRING"},
                },
                "required": ["name", "type", "description"],
            },
        },
        "relations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "from": {"type": "STRING"},
                    "to": {"type": "STRING"},
                    "type": {"type": "STRING"},
                },
                "required": ["from", "to", "type"],
            },
        },
    },
    "required": ["concepts", "relations"],
}


class Extractor(Protocol):
    model: str

    async def extract(self, path: str, text: str) -> dict[str, Any]: ...


class GeminiExtractor:
    def __init__(self, project: str, location: str, model: str, concurrency: int = 4, client=None) -> None:
        if client is None:
            from google import genai

            client = genai.Client(vertexai=True, project=project, location=location)
        self.client = client
        self.model = model
        self._slots = asyncio.Semaphore(concurrency)

    async def extract(self, path: str, text: str) -> dict[str, Any]:
        from google.genai import errors, types

        config = types.GenerateContentConfig(
            temperature=0, response_mime_type="application/json", response_schema=SCHEMA
        )
        prompt = PROMPT.format(max=MAX_CONCEPTS, path=path, text=text[:MAX_CHARS])
        delay = 2.0
        for attempt in range(5):
            try:
                async with self._slots:
                    response = await self.client.aio.models.generate_content(
                        model=self.model, contents=prompt, config=config
                    )
                return clean(json.loads(response.text or "{}"))
            except errors.APIError as exc:
                if exc.code not in (429, 500, 503) or attempt == 4:
                    raise
                await asyncio.sleep(delay)
                delay *= 2
        raise AssertionError("unreachable")


def clean(raw: Any) -> dict[str, Any]:
    """Only well-formed concepts (at most MAX_CONCEPTS) and relations between them."""
    concepts, names = [], set()
    for c in (raw or {}).get("concepts") or ():
        name = str(c.get("name") or "").strip()[:120] if isinstance(c, Mapping) else ""
        if name and slug(name) not in names and len(concepts) < MAX_CONCEPTS:
            names.add(slug(name))
            concepts.append(
                {
                    "name": name,
                    "type": str(c.get("type") or "")[:40],
                    "description": str(c.get("description") or "")[:300],
                }
            )
    relations = []
    for r in (raw or {}).get("relations") or ():
        if not isinstance(r, Mapping):
            continue
        a, b, kind = (str(r.get(k) or "").strip() for k in ("from", "to", "type"))
        if slug(a) in names and slug(b) in names and slug(a) != slug(b) and kind:
            relations.append({"from": a, "to": b, "type": re.sub(r"[^a-z0-9_]+", "_", kind.lower()).strip("_")[:40]})
    return {"concepts": concepts, "relations": relations}


def concept_id(source_id: str, name: str) -> str:
    return f"{source_id}:concept:{slug(name)}"


def concept_graph(source_id: str, classification: str, per_file: Mapping[str, tuple[str, dict[str, Any]]]) -> Graph:
    """Merges the extractions of one source's files ({path: (file hash, extraction)}) into concept entities,
    `mentions` edges from each file and the relations between concepts."""
    g = Graph()
    concepts: dict[str, Entity] = {}
    relations: set[tuple[str, str, str]] = set()
    for path in sorted(per_file):
        file_hash, found = per_file[path]
        for c in found.get("concepts") or ():
            cid = concept_id(source_id, c["name"])
            concepts.setdefault(
                cid, Entity(cid, source_id, classification, "concept", c["name"], "", c.get("description", ""))
            )
            g.edges.append(Edge(source_id, classification, file_entity_id(source_id, path), cid, MENTIONS, file_hash))
        for r in found.get("relations") or ():
            relations.add((concept_id(source_id, r["from"]), concept_id(source_id, r["to"]), r["type"]))
    g.entities.extend(concepts[k] for k in sorted(concepts))
    for a, b, kind in sorted(relations):
        if a in concepts and b in concepts:
            g.edges.append(Edge(source_id, classification, a, b, kind))
    return g


@dataclass(frozen=True)
class CachedExtraction:
    source_id: str
    classification: str
    path: str
    file_hash: str
    model: str
    result: dict[str, Any]
