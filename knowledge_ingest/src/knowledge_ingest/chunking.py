"""Splitting a file into chunks: Markdown by heading, everything else by windows of lines."""

import re
from dataclasses import dataclass

CHUNKER = "v1"  # change when chunking changes, so the next run re-chunks and re-embeds
MAX_CHARS = 2000
WINDOW_LINES = 60
OVERLAP_LINES = 5
MARKDOWN = (".md", ".markdown", ".mdx")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")


@dataclass(frozen=True)
class Piece:
    start_line: int  # 1-based, inclusive
    end_line: int
    heading: str  # "Title > Section", or "" outside any heading
    text: str


@dataclass(frozen=True)
class Heading:
    line: int
    level: int
    title: str


def headings(text: str) -> list[Heading]:
    """Markdown headings outside fenced code blocks."""
    found, fenced = [], False
    for n, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        match = None if fenced else HEADING.match(line)
        if match:
            found.append(Heading(n, len(match.group(1)), match.group(2).strip()))
    return found


def _windows(lines: list[str], first: int, heading: str) -> list[Piece]:
    pieces, start = [], 0
    while start < len(lines):
        end, size = start, 0
        while end < len(lines) and end - start < WINDOW_LINES and (size + len(lines[end]) <= MAX_CHARS or end == start):
            size += len(lines[end]) + 1
            end += 1
        text = "\n".join(lines[start:end])
        if text.strip():
            pieces.append(Piece(first + start, first + end - 1, heading, text[: MAX_CHARS * 2]))
        if end >= len(lines):
            break
        start = max(end - OVERLAP_LINES, start + 1)
    return pieces


def chunk(path: str, text: str) -> list[Piece]:
    lines = text.splitlines()
    if not path.lower().endswith(MARKDOWN):
        return _windows(lines, 1, "")
    marks = headings(text)
    bounds = [h.line for h in marks]
    if not bounds or bounds[0] != 1:
        bounds = [1, *bounds]
    pieces: list[Piece] = []
    trail: list[Heading] = []
    for i, start in enumerate(bounds):
        end = bounds[i + 1] - 1 if i + 1 < len(bounds) else len(lines)
        mark = next((h for h in marks if h.line == start), None)
        if mark:
            trail = [h for h in trail if h.level < mark.level] + [mark]
        title = " > ".join(h.title for h in trail)
        section = lines[start - 1 : end]
        if len("\n".join(section)) <= MAX_CHARS:
            text_ = "\n".join(section)
            if text_.strip():
                pieces.append(Piece(start, end, title, text_))
        else:
            pieces.extend(_windows(section, start, title))
    return pieces
