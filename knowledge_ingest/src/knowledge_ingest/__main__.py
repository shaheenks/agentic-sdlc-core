"""sdlc-knowledge-ingest: one ingest run, from the active configuration bundle into a JSONL store.

    sdlc-knowledge-ingest --env local --config .data/config --out .data/knowledge [--source ID ...]
                          [--root .] [--previous DIR] [--no-extract]

Sources come from the active bundle in `--config` (a folder or gs://<configuration bucket>). Folder sources are
read under `--root` (the build checkout). The previous store (default: `--out`) supplies unchanged files'
chunks and embeddings. Exits 1 when a source failed; the store is still written, with the failed sources'
previous records.
"""

import argparse
import asyncio
import logging
import os
import sys
import uuid
from pathlib import Path

from sdlc_config_store import ConfigStore, ConfigUnavailable, source_from_url
from sdlc_knowledge import embedder_from_env
from sdlc_logging import configure_logging

from knowledge_ingest import NAME
from knowledge_ingest.extract import GeminiExtractor
from knowledge_ingest.fetch import read_secret_from
from knowledge_ingest.pipeline import Previous, ingest, write

# Embeddings run in the platform's region; this model has no europe-west3 endpoint, so it runs in `eu`.
DEFAULT_EXTRACT_MODEL = "gemini-3.8-flash"
DEFAULT_EXTRACT_LOCATION = "eu"


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sdlc-knowledge-ingest")
    p.add_argument("--env", default=os.environ.get("SDLC_ENV", "local"))
    p.add_argument("--config", default=os.environ.get("CONFIG_SOURCE"), help="folder or gs://<config bucket>")
    p.add_argument("--out", type=Path, default=Path(os.environ.get("KNOWLEDGE_PATH", ".data/knowledge")))
    p.add_argument("--previous", type=Path, help="the previous store (default: --out)")
    p.add_argument("--root", type=Path, default=Path("."), help="where folder sources are read")
    p.add_argument("--source", action="append", help="ingest only this source; the others keep their records")
    p.add_argument("--no-extract", action="store_true", help="no Gemini extraction in this run")
    return p


def main(argv: list[str] | None = None) -> int:
    configure_logging(NAME)
    for noisy in ("httpx", "httpx2", "google_genai"):  # one line per model request otherwise
        logging.getLogger(noisy).setLevel(logging.WARNING)
    log = logging.getLogger(NAME)
    args = _parser().parse_args(argv)
    if not args.config:
        print("error: --config or CONFIG_SOURCE must name the configuration store", file=sys.stderr)
        return 2
    try:
        bundle = ConfigStore(source_from_url(args.config), args.env).load()
    except ConfigUnavailable as exc:
        print(f"error: no active configuration: {exc}", file=sys.stderr)
        return 2
    sources = bundle.config.get("sources") or {}
    unknown = sorted(set(args.source or ()) - set(sources))
    if unknown:
        print(f"error: unknown sources: {', '.join(unknown)}", file=sys.stderr)
        return 2
    embedder = embedder_from_env()
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    extract_model = os.environ.get("EXTRACT_MODEL", DEFAULT_EXTRACT_MODEL)
    extractor = None
    if not args.no_extract and os.environ.get("EXTRACTION", "vertex") == "vertex":
        if not project:
            print("error: GOOGLE_CLOUD_PROJECT must be set for extraction (or --no-extract)", file=sys.stderr)
            return 2
        extractor = GeminiExtractor(
            project, os.environ.get("EXTRACT_LOCATION", DEFAULT_EXTRACT_LOCATION), extract_model
        )
    result = asyncio.run(
        ingest(
            sources,
            root=args.root,
            previous=Previous.read(args.previous or args.out),
            embedder=embedder,
            extractor=extractor,
            read_secret=read_secret_from(os.environ, project),
            only=set(args.source) if args.source else None,
            context={"run_id": uuid.uuid4().hex, "env": args.env, "config_version": bundle.version},
        )
    )
    write(args.out, result)
    s = result.store
    log.info(
        "ingest finished: %d sources, %d chunks, %d entities, %d edges, failed: %s",
        len(s.manifest["sources"]),
        len(s.chunks),
        len(s.entities),
        len(s.edges),
        ", ".join(result.failed) or "none",
    )
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
