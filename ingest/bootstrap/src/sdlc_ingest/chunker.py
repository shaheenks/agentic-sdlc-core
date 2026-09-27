"""Split files into retrievable chunks.

Strategies (Source.spec.ingest.chunking.strategy):
  markdown  split at headings; long sections are split further by size
  code      split at top-level definitions (Python def/class, Terraform/HCL blocks); size fallback
  fixed     line windows of ~max_tokens with `overlap` tokens carried over
  auto      markdown for .md, code for .py/.tf/.hcl, fixed otherwise
Sizes are approximate: tokens are estimated as characters / 4.
"""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    start_line: int  # 1-based, inclusive
    end_line: int
    heading: str | None
    content: str


_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_CODE_START = re.compile(
    r"^(?:(?:async\s+)?def\s+\w+|class\s+\w+|resource\s+\"|module\s+\"|data\s+\"|variable\s+\""
    r"|output\s+\"|locals\s*\{|provider\s+\")"
)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def chunk_text(
    path: str, text: str, strategy: str = "auto", max_tokens: int = 400, overlap: int = 40
) -> list[Chunk]:
    lines = text.splitlines()
    if not lines:
        return []
    if strategy == "auto":
        suffix = PurePosixPath(path).suffix.lower()
        strategy = {".md": "markdown", ".py": "code", ".tf": "code", ".hcl": "code"}.get(
            suffix, "fixed"
        )
    if strategy == "markdown":
        sections = _markdown_sections(lines)
    elif strategy == "code":
        sections = _code_sections(lines)
    else:
        sections = [(1, len(lines), None)]
    chunks: list[Chunk] = []
    for start, end, heading in sections:
        for s, e in _windows(lines, start, end, max_tokens, overlap):
            content = "\n".join(lines[s - 1 : e]).strip()
            if content:
                chunks.append(Chunk(len(chunks), s, e, heading, content))
    return chunks


def _markdown_sections(lines: list[str]) -> list[tuple[int, int, str | None]]:
    starts: list[tuple[int, str | None]] = [(1, None)]
    trail: list[str] = []
    in_fence = False
    for number, line in enumerate(lines, start=1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
        match = None if in_fence else _HEADING.match(line)
        if match:
            level = len(match.group(1))
            trail = [*trail[: level - 1], match.group(2)]
            starts.append((number, " > ".join(trail)))
    return _close(starts, len(lines), lines)


def _code_sections(lines: list[str]) -> list[tuple[int, int, str | None]]:
    starts: list[tuple[int, str | None]] = [(1, None)]
    for number, line in enumerate(lines, start=1):
        if _CODE_START.match(line):
            # attach decorators / comments directly above the definition
            begin = number
            while begin > 1 and lines[begin - 2].lstrip().startswith(("@", "#")):
                begin -= 1
            starts.append((begin, line.strip().rstrip(":{").strip()))
    return _close(starts, len(lines), lines)


MIN_SECTION_TOKENS = 25  # smaller sections (e.g. a lone title) are merged into the next one


def _close(starts, total, lines=None) -> list[tuple[int, int, str | None]]:
    starts = sorted({s: h for s, h in starts}.items())
    sections = []
    for i, (start, heading) in enumerate(starts):
        end = (starts[i + 1][0] - 1) if i + 1 < len(starts) else total
        if end >= start:
            sections.append((start, end, heading))
    if lines is None:
        return sections
    merged: list[tuple[int, int, str | None]] = []
    carry: int | None = None  # start line of a tiny section waiting to be merged forward
    for start, end, heading in sections:
        begin = carry if carry is not None else start
        size = estimate_tokens("\n".join(lines[begin - 1 : end]))
        if size < MIN_SECTION_TOKENS and end < total:
            carry = begin
            continue
        merged.append((begin, end, heading))
        carry = None
    return merged


def _windows(lines, start, end, max_tokens, overlap):
    """Split lines[start..end] into windows of about max_tokens, carrying `overlap` tokens."""
    windows, s = [], start
    while s <= end:
        size, e = 0, s
        while e <= end:
            size += estimate_tokens(lines[e - 1]) + 1
            if size > max_tokens and e > s:
                e -= 1
                break
            e += 1
        e = min(e, end)
        windows.append((s, e))
        if e >= end:
            break
        back, carried = e, 0
        while overlap and back > s and carried < overlap:
            carried += estimate_tokens(lines[back - 1]) + 1
            back -= 1
        s = max(back + 1, s + 1) if overlap else e + 1
    return windows
