import asyncio
import json
from types import SimpleNamespace

import pytest
from sdlc_knowledge import (
    DOCUMENT,
    Chunk,
    Edge,
    Entity,
    HashEmbedder,
    Store,
    StoreError,
    VertexEmbedder,
    embedder_from_env,
    read_store,
    tokens,
    write_store,
)


def store():
    return Store(
        {"run": "r1"},
        [Chunk("s:a.md#0", "s", "internal", "a.md", "https://x/a.md", 1, 3, "A", "text", "h", (0.6, 0.8))],
        [Entity("s:file:a.md", "s", "internal", "file", "a.md", "a.md")],
        [Edge("s", "internal", "s:source", "s:file:a.md", "contains")],
    )


def test_store_round_trips(tmp_path):
    write_store(tmp_path, store())
    loaded = read_store(tmp_path)
    assert loaded.chunks == store().chunks
    assert loaded.entities == store().entities and loaded.edges == store().edges
    assert loaded.manifest["run"] == "r1"


def test_a_record_without_its_source_is_refused(tmp_path):
    write_store(tmp_path, store())
    record = json.loads((tmp_path / "chunks.jsonl").read_text())
    record["source_id"] = ""
    (tmp_path / "chunks.jsonl").write_text(json.dumps(record) + "\n")
    with pytest.raises(StoreError, match="without source_id"):
        read_store(tmp_path)
    with pytest.raises(StoreError, match="without classification"):
        write_store(tmp_path, Store({}, [], [Entity("x", "s", "", "file", "x")], []))


def test_a_missing_store_is_an_error(tmp_path):
    with pytest.raises(StoreError):
        read_store(tmp_path)


def test_tokens_split_snake_case():
    assert tokens("Read artifact_save now") == ["read", "artifact_save", "artifact", "save", "now"]


def test_hash_embedder_is_deterministic_and_normalised():
    embedder = HashEmbedder(64)
    a, b, c = asyncio.run(embedder.embed(["artifact store", "artifact store", "jira tickets"], DOCUMENT))
    assert a == b and a != c
    assert abs(sum(v * v for v in a) - 1) < 1e-9


def test_vertex_embedder_asks_for_the_task_and_size_and_normalises():
    calls = []

    async def embed_content(model, contents, config):
        calls.append((model, contents, config.task_type, config.output_dimensionality))
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[3.0, 4.0])])

    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(embed_content=embed_content)))
    embedder = VertexEmbedder("p", client=client, dimensions=2)
    assert asyncio.run(embedder.embed(["x"], DOCUMENT)) == [[0.6, 0.8]]
    assert calls == [("gemini-embedding-001", "x", DOCUMENT, 2)]


def test_embedder_from_env():
    assert embedder_from_env({"EMBEDDINGS": "hash"}).model == "hash-v1"
    with pytest.raises(SystemExit):
        embedder_from_env({"EMBEDDINGS": "vertex"})
    with pytest.raises(SystemExit):
        embedder_from_env({"EMBEDDINGS": "other"})
