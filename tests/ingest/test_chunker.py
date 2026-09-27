"""Chunker and file walker (sdlc_ingest)."""

from pathlib import Path

from sdlc_ingest.chunker import chunk_text
from sdlc_ingest.files import walk

MD = """# Refunds

Intro paragraph about refunds that is long enough to stand on its own as a section here.

## Retries
Refunds are retried with exponential backoff, at most five attempts,
reusing the idempotency key so the provider never charges the card twice.

## Partial refunds
Several partial refunds are allowed while the sum stays at or below the captured amount.
"""

PY = '''"""module doc"""
import os


@decorator
def first(a):
    total = sum(range(a))
    message = f"first computed a total of {total} for input {a}"
    return message


class Second:
    def method(self):
        value = "second method returns a fairly long string value here"
        return value
'''


def test_markdown_splits_on_headings_with_heading_path():
    chunks = chunk_text("docs/refunds.md", MD)
    headings = [c.heading for c in chunks]
    assert headings == ["Refunds", "Refunds > Retries", "Refunds > Partial refunds"]
    assert chunks[1].content.startswith("## Retries") and chunks[1].start_line == 5


def test_tiny_sections_merge_forward():
    chunks = chunk_text("x.md", "# Title\n\n## Body\n" + "word " * 60)
    assert len(chunks) == 1 and chunks[0].content.startswith("# Title")


def test_code_splits_on_definitions_and_keeps_decorators():
    chunks = chunk_text("m.py", PY + "\n" + "\n".join(f"x{i} = {i}" for i in range(40)))
    assert [c.heading for c in chunks] == ["def first(a)", "class Second"]
    assert "@decorator\ndef first(a):" in chunks[0].content  # decorator stays with its def
    assert chunks[1].content.startswith("class Second")


def test_large_sections_are_windowed_with_line_ranges():
    text = "\n".join(f"line {i} " + "x" * 60 for i in range(200))
    chunks = chunk_text("big.txt", text, "fixed", max_tokens=200, overlap=20)
    assert len(chunks) > 5
    assert all(c.start_line <= c.end_line for c in chunks)
    assert chunks[-1].end_line == 200
    assert chunks[1].start_line <= chunks[0].end_line  # overlap


def test_walk_applies_include_exclude_and_skips_binary(tmp_path: Path):
    (tmp_path / "docs/fixtures").mkdir(parents=True)
    (tmp_path / "docs/a.md").write_text("# a")
    (tmp_path / "top.md").write_text("# top")
    (tmp_path / "skip.txt").write_text("nope")
    (tmp_path / "docs/fixtures/f.md").write_text("# fixture")
    (tmp_path / "bin.md").write_bytes(b"\x00\x01binary")
    files = [f.path for f in walk(tmp_path, ("**/*.md",), ("**/fixtures/**",))]
    assert files == ["docs/a.md", "top.md"]
