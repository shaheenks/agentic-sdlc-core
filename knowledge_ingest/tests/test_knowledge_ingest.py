"""The ingest pipeline (FR-KNOW-001, FR-KNOW-003; DEC-0011), with the hash embedder and a fake extractor."""

import asyncio
import json
import shutil
import subprocess

import pytest
from knowledge_ingest.__main__ import main
from knowledge_ingest.chunking import chunk
from knowledge_ingest.fetch import FetchError, fetch_git, link_for, selector
from knowledge_ingest.graph import file_graph, modules_of
from knowledge_ingest.pipeline import Previous, ingest
from sdlc_config_store import DirSource, make_bundle, make_pointer
from sdlc_knowledge import HashEmbedder, read_store

DOC = """# Payments

Intro text.

## Refunds

Refunds call the [ledger](ledger.md#top) and [missing](nope.md).

```
# not a heading
```
"""
SOURCES = {
    "docs": {
        "name": "Docs",
        "description": "-",
        "kind": "folder",
        "location": "docs",
        "include": ["*.md", "**/*.py"],
        "exclude": ["skip.md"],
        "classification": "internal",
        "link": "https://example.test/{path}",
    }
}


class FakeExtractor:
    model = "fake-1"

    def __init__(self):
        self.seen = []

    async def extract(self, path, text):
        self.seen.append(path)
        if "boom" in text:
            raise RuntimeError("model failed")
        return {
            "concepts": [
                {"name": "Refund Service", "type": "service", "description": "-"},
                {"name": "Ledger", "type": "system", "description": "-"},
            ],
            "relations": [{"from": "Refund Service", "to": "Ledger", "type": "calls"}],
        }


class CountingEmbedder(HashEmbedder):
    def __init__(self):
        super().__init__(16)
        self.count = 0

    async def embed(self, texts, task):
        self.count += len(texts)
        return await super().embed(texts, task)


@pytest.fixture
def root(tmp_path):
    docs = tmp_path / "root" / "docs"
    (docs / "pkg").mkdir(parents=True)
    (docs / "payments.md").write_text(DOC, encoding="utf-8")
    (docs / "ledger.md").write_text("# Ledger\n\nBalances.\n", encoding="utf-8")
    (docs / "skip.md").write_text("# Skipped\n", encoding="utf-8")
    (docs / "image.md").write_bytes(b"\x00\x01binary")
    (docs / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (docs / "pkg" / "refunds.py").write_text(
        'from pkg import ledger\n\n\nclass Refund:\n    """A refund."""\n\n    def apply(self):\n        pass\n',
        encoding="utf-8",
    )
    (docs / "pkg" / "ledger.py").write_text("def post():\n    pass\n", encoding="utf-8")
    return tmp_path / "root"


def run(root, previous=None, embedder=None, extractor=None, sources=SOURCES, only=None):
    return asyncio.run(
        ingest(
            sources,
            root=root,
            previous=previous or Previous(),
            embedder=embedder or HashEmbedder(16),
            extractor=extractor,
            read_secret=lambda name: "unused",
            only=only,
        )
    )


def test_every_record_is_tagged_and_located(root):
    result = run(root)
    s = result.store
    assert {c.path for c in s.chunks} == {"payments.md", "ledger.md", "pkg/refunds.py", "pkg/ledger.py"}
    assert all(r.source_id == "docs" and r.classification == "internal" for r in [*s.chunks, *s.entities, *s.edges])
    refunds = next(c for c in s.chunks if c.heading == "Payments > Refunds")
    assert refunds.link == "https://example.test/payments.md" and refunds.start_line == 5
    status = s.manifest["sources"]["docs"]
    assert status["status"] == "ok" and status["files"] == 5 and status["skipped"] == 2  # skip.md, image.md
    assert s.manifest["embedding"] == {"model": "hash-v1", "dimensions": 16}


def test_structural_graph(root):
    s = run(root).store
    kinds = {(e.from_id, e.to_id, e.kind) for e in s.edges}
    assert ("docs:source", "docs:file:payments.md", "contains") in kinds
    assert ("docs:file:payments.md", "docs:file:ledger.md", "links_to") in kinds  # nope.md does not exist
    assert ("docs:file:pkg/refunds.py", "docs:file:pkg/ledger.py", "imports") in kinds
    assert ("docs:symbol:pkg/refunds.py:Refund", "docs:symbol:pkg/refunds.py:Refund.apply", "contains") in kinds
    sections = [e.name for e in s.entities if e.kind == "section" and e.path == "payments.md"]
    assert sections == ["Payments", "Refunds"]  # the fenced '# not a heading' is not one


def test_re_ingest_embeds_only_changed_files_and_drops_removed_ones(root):
    embedder = CountingEmbedder()
    first = run(root, embedder=embedder)
    assert embedder.count == len(first.store.chunks)
    (root / "docs" / "ledger.md").write_text("# Ledger\n\nBalances and holds.\n", encoding="utf-8")
    (root / "docs" / "pkg" / "ledger.py").unlink()
    embedder.count = 0
    second = run(root, previous=Previous(first.store, first.extractions), embedder=embedder)
    assert embedder.count == 1  # ledger.md's one chunk
    assert "pkg/ledger.py" not in {c.path for c in second.store.chunks}
    assert second.store.manifest["sources"]["docs"]["reused"] == len(second.store.chunks) - 1
    assert not any(e.to_id == "docs:file:pkg/ledger.py" for e in second.store.edges)


def test_a_new_embedding_model_re_embeds_everything(root):
    first = run(root)
    embedder = CountingEmbedder()
    embedder.model = "other"
    second = run(root, previous=Previous(first.store, first.extractions), embedder=embedder)
    assert embedder.count == len(second.store.chunks)


def test_extraction_is_cached_per_file_and_survives_a_failure(root):
    (root / "docs" / "ledger.md").write_text("# Ledger\n\nboom\n", encoding="utf-8")
    extractor = FakeExtractor()
    first = run(root, extractor=extractor)
    status = first.store.manifest["sources"]["docs"]
    assert status["extracted"] == 4 and status["extraction_errors"] == 1  # five files, ledger.md failed
    concepts = {e.id for e in first.store.entities if e.kind == "concept"}
    assert concepts == {"docs:concept:refund-service", "docs:concept:ledger"}
    assert ("docs:concept:refund-service", "docs:concept:ledger", "calls") in {
        (e.from_id, e.to_id, e.kind) for e in first.store.edges
    }
    extractor.seen.clear()
    run(root, previous=Previous(first.store, first.extractions), extractor=extractor)
    assert extractor.seen == ["ledger.md"]  # only the file that failed is asked again


def test_a_failed_source_keeps_its_previous_records(root):
    first = run(root)
    shutil.rmtree(root / "docs")
    second = run(root, previous=Previous(first.store, first.extractions))
    assert second.failed == ["docs"]
    assert second.store.chunks == first.store.chunks
    assert second.store.manifest["sources"]["docs"]["status"] == "failed"


def test_only_selected_sources_are_read(root):
    sources = {**SOURCES, "more": {**SOURCES["docs"], "name": "More", "location": "missing"}}
    first = run(root, sources={"docs": SOURCES["docs"]})
    second = run(root, previous=Previous(first.store, first.extractions), sources=sources, only={"more"})
    assert second.failed == ["more"]
    assert second.store.manifest["sources"]["docs"] == first.store.manifest["sources"]["docs"]
    assert {c.source_id for c in second.store.chunks} == {"docs"}


def test_folder_outside_root_is_refused(root):
    result = run(root, sources={"x": {**SOURCES["docs"], "location": "../.."}})
    assert result.failed == ["x"] and "outside" in result.store.manifest["sources"]["x"]["error"]


def test_chunking_splits_long_files_with_line_ranges():
    pieces = chunk("a.py", "\n".join(f"line {i}" for i in range(200)))
    assert pieces[0].start_line == 1 and pieces[0].end_line == 60
    assert pieces[1].start_line == 56  # five lines of overlap
    assert pieces[-1].end_line == 200


def test_selector_patterns():
    wanted = selector(["*.md", "src/**/*.py"], ["**/vendor/**", "CHANGELOG.md"])
    assert wanted("docs/a.md") and wanted("src/x/y.py") and wanted("src/y.py")
    assert not wanted("CHANGELOG.md") and not wanted("lib/vendor/a.md") and not wanted("other/y.py")


def test_links():
    git = {"kind": "git", "location": "https://github.com/o/r.git", "ref": "main"}
    assert link_for(git, "a/b.md", "abc") == "https://github.com/o/r/blob/abc/a/b.md"
    assert link_for({"kind": "folder", "location": "x"}, "a.md", "") == "a.md"


def test_relative_python_imports():
    paths = ["pkg/__init__.py", "pkg/a.py", "pkg/b.py"]
    g = file_graph(
        "s", "internal", "pkg/a.py", "from . import b\nfrom .b import thing\n", "h", set(paths), modules_of(paths)
    )
    assert {(e.to_id, e.kind) for e in g.edges if e.kind == "imports"} == {("s:file:pkg/b.py", "imports")}


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_git_source_at_a_ref(tmp_path):
    repo = tmp_path / "upstream"
    repo.mkdir()
    try:
        _git(repo, "init", "-q", "-b", "main")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git is not available")
    (repo / "README.md").write_text("# Hello\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.test", "commit", "-q", "-m", "one")
    fetched = fetch_git({"kind": "git", "location": repo.as_uri(), "ref": "main"}, lambda n: "")
    assert fetched.files == {"README.md": "# Hello\n"} and len(fetched.revision) == 40
    with pytest.raises(FetchError, match="git fetch failed"):
        fetch_git({"kind": "git", "location": repo.as_uri(), "ref": "nope"}, lambda n: "")


def test_cli_reads_the_active_bundle_and_writes_the_store(root, tmp_path, monkeypatch):
    config = tmp_path / "config"
    doc = make_bundle("local", {"sources": SOURCES})
    DirSource(config).write(f"bundles/{doc['version']}.json", json.dumps(doc).encode())
    DirSource(config).write("active.json", json.dumps(make_pointer(doc["version"], "t", None)).encode())
    monkeypatch.setenv("EMBEDDINGS", "hash")
    out = tmp_path / "out"
    args = ["--env", "local", "--config", str(config), "--root", str(root), "--out", str(out), "--no-extract"]
    assert main(args) == 0
    store = read_store(out)
    assert store.manifest["config_version"] == doc["version"] and store.chunks
    assert main([*args, "--source", "ghost"]) == 2


def test_markdown_titles_describe_files():
    from knowledge_ingest.graph import title

    assert title("a.md", '---\ntype: X\ntitle: "user_agent_mcp"\n---\n\n# Purpose\n') == "user_agent_mcp"
    assert title("b.md", "intro\n\n# First heading\n") == "First heading"
    assert title("c.py", "# comment") == ""
