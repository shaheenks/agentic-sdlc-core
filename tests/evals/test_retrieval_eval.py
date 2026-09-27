"""Stage 6 gate: hybrid (vector + knowledge graph) retrieval >= vector-only, on the real index.

Opt-in (live Vertex query embeddings against the ingested dev database):
    SDLC_EVAL=1 uv run --env-file .env pytest tests/evals -s
Ingest first: docker compose run --rm ingest run --all
(or on the host: uv run --env-file .env sdlc-ingest run --all).

Metrics by file: recall@5 / recall@3 = share of a question's expected files among the first 5 / 3
distinct files; mrr = mean reciprocal rank of the expected files (within the first 10 results).
Variants: vector (search_knowledge as-is: top 5 chunks), vector+dedup (best chunk per file, the
same diversity step graph_query uses, so the graph's own contribution is visible), hybrid hops=1/2.
The eval reads everything (admin persona): it measures retrieval quality, not access control.
"""

import os
from pathlib import Path

import psycopg
import pytest
import yaml
from sdlc_config import load_snapshot, resolve
from sdlc_db import GeminiEmbedder, conninfo, graph_search, search

from tests.support.db import run
from tests.support.entra import TEST_ENV

pytestmark = pytest.mark.skipif(
    os.environ.get("SDLC_EVAL") != "1", reason="set SDLC_EVAL=1 (live Vertex + ingested dev DB)"
)

K = 5
DEPTH = 10  # results fetched per variant (MRR is computed over these)
QUESTIONS = yaml.safe_load(
    (Path(__file__).parent / "retrieval_questions.yaml").read_text(encoding="utf-8")
)["questions"]
VARIANTS = ("vector", "vector+dedup", "hybrid h1", "hybrid h2")
METRICS = ("recall@5", "recall@3", "mrr")


def ranked_files(hits) -> list[str]:
    files: list[str] = []
    for h in hits:
        name = f"{h.source_id}:{h.path}"
        if name not in files:
            files.append(name)
    return files


def scores(expected: list[str], hits) -> dict[str, float]:
    files = ranked_files(hits)
    return {
        "recall@5": len(set(expected) & set(files[:5])) / len(expected),
        "recall@3": len(set(expected) & set(files[:3])) / len(expected),
        "mrr": sum(1 / (files.index(e) + 1) for e in expected if e in files) / len(expected),
    }


def dedup(hits):
    seen, out = set(), []
    for h in hits:
        if (h.source_id, h.path) not in seen:
            seen.add((h.source_id, h.path))
            out.append(h)
    return out


async def evaluate(policy, embedder):
    rows = []
    async with await psycopg.AsyncConnection.connect(conninfo("app")) as conn:
        for item in QUESTIONS:
            question = item["q"]
            [vec] = embedder.embed([question], "query")
            variants = {
                "vector": await search(conn, policy, vec, K),  # what search_knowledge returns
                "vector+dedup": dedup(await search(conn, policy, vec, 20))[:DEPTH],
                "hybrid h1": (await graph_search(conn, policy, vec, question, DEPTH, 1)).hits,
                "hybrid h2": (await graph_search(conn, policy, vec, question, DEPTH, 2)).hits,
            }
            rows.append(
                {
                    "q": question,
                    "multi": item.get("hops") == "multi",
                    **{v: scores(item["expect"], hits) for v, hits in variants.items()},
                }
            )
    return rows


def report(rows) -> dict[str, dict[str, dict[str, float]]]:
    groups = {
        "all": rows,
        "multi-hop": [r for r in rows if r["multi"]],
        "single": [r for r in rows if not r["multi"]],
    }
    summary = {
        g: {v: {m: sum(r[v][m] for r in subset) / len(subset) for m in METRICS} for v in VARIANTS}
        for g, subset in groups.items()
        if subset
    }
    print(f"\nretrieval eval: {len(rows)} questions, metric per variant")
    print(f"{'':22}" + "".join(f"{v:>14}" for v in VARIANTS))
    for g, values in summary.items():
        for m in METRICS:
            print(f"{g + ' ' + m:22}" + "".join(f"{values[v][m]:>14.3f}" for v in VARIANTS))
    print("\nper question, recall@5 (vector / vector+dedup / hybrid h1 / hybrid h2):")
    for r in rows:
        marks = " ".join(f"{r[v]['recall@5']:.2f}" for v in VARIANTS)
        print(f"  {'M' if r['multi'] else ' '} {marks}  {r['q'][:80]}")
    return summary


def test_hybrid_retrieval_is_at_least_as_good_as_vector_only(config_dir):
    snap = load_snapshot(config_dir, "local", TEST_ENV)
    policy = resolve(snap, ["platform-admins"])
    embedder = GeminiEmbedder(snap.platform.embedding_model, snap.platform.embedding_dimensions)
    summary = report(run(evaluate(policy, embedder)))
    # Gate (docs/IMPLEMENTATION_PLAN.md Stage 6): hybrid >= vector-only on recall@5.
    for group in ("all", "multi-hop"):
        assert summary[group]["hybrid h1"]["recall@5"] >= summary[group]["vector"]["recall@5"]
