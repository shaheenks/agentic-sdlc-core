"""sdlc-ingest CLI.

  sdlc-ingest run --source <id> [--source <id> ...] | --all  [--dry-run] [--force]

Config: SDLC_CONFIG_DIR (default: repo config/), SDLC_ENV (default: local). Source locations
resolve relative to the parent of the config dir (the repo root). Database: the sdlc_ingest role
(PG* env + SDLC_INGEST_PASSWORD). Embeddings: platform.yaml knowledge.embedding via Vertex AI /
Gemini API (google-genai env: GOOGLE_GENAI_USE_VERTEXAI, GOOGLE_CLOUD_PROJECT, ...). Graph
extraction: platform.yaml knowledge.graph.model, for sources with spec.ingest.graph.enabled.
After changing a source's graph settings, re-run with --force (model output is cached, so only
chunks whose extraction inputs changed call the model again).
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import psycopg
from sdlc_config import ConfigError, load_snapshot
from sdlc_config.store import DEFAULT_CONFIG_DIR
from sdlc_db.connect import conninfo
from sdlc_db.embedding import GeminiEmbedder

from sdlc_ingest.extract import GeminiExtractor
from sdlc_ingest.pipeline import ingest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdlc-ingest")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="ingest sources declared in config/sources")
    which = run.add_mutually_exclusive_group(required=True)
    which.add_argument("--source", action="append", help="source id (repeatable)")
    which.add_argument("--all", action="store_true")
    run.add_argument("--dry-run", action="store_true", help="walk + chunk only; no DB, no API")
    run.add_argument(
        "--force", action="store_true", help="re-chunk and re-embed unchanged files too"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(message)s")
    config_dir = Path(os.environ.get("SDLC_CONFIG_DIR", DEFAULT_CONFIG_DIR))
    try:
        snapshot = load_snapshot(config_dir, os.environ.get("SDLC_ENV", "local"))
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1
    platform = snapshot.platform
    embedder = GeminiEmbedder(platform.embedding_model, platform.embedding_dimensions)
    wanted = list(snapshot.sources) if args.all else args.source
    needs_graph = any(snapshot.sources[s].graph_enabled for s in wanted if s in snapshot.sources)
    extractor = (
        GeminiExtractor(platform.graph_model, platform.graph_thinking_level)
        if needs_graph and not args.dry_run
        else None
    )
    reports = run_async(
        _run(
            snapshot,
            embedder,
            config_dir.parent,
            None if args.all else args.source,
            args.dry_run,
            args.force,
            extractor,
        )
    )
    for r in reports:
        print(
            f"{r.source_id}: files={r.files_seen} changed={r.files_changed} "
            f"unchanged={r.files_unchanged} deleted={r.files_deleted} chunks={r.chunks_written} "
            f"entities={r.entities_written} relations={r.relations_written} "
            f"llm_calls={r.extraction_calls}" + (f" commit={r.commit[:12]}" if r.commit else "")
        )
        for error in r.errors:
            print(f"  error: {error}", file=sys.stderr)
    return 1 if any(r.errors for r in reports) else 0


def run_async(coro):
    """psycopg's async mode needs a selector event loop; Windows defaults to Proactor."""
    if sys.platform == "win32":
        return asyncio.run(coro, loop_factory=asyncio.SelectorEventLoop)
    return asyncio.run(coro)


async def _run(snapshot, embedder, repo_root, source_ids, dry_run, force=False, extractor=None):
    if dry_run:  # walk + chunk only: no database, no embedding calls
        return await ingest(None, snapshot, embedder, repo_root, source_ids, dry_run=True)
    async with await psycopg.AsyncConnection.connect(conninfo("ingest"), autocommit=True) as conn:
        return await ingest(
            conn, snapshot, embedder, repo_root, source_ids, dry_run, force, extractor
        )


if __name__ == "__main__":
    sys.exit(main())
