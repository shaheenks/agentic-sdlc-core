"""Walk a local_folder source: include/exclude globs, text files only, stable relative paths."""

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

MAX_FILE_BYTES = 1_000_000


@dataclass(frozen=True)
class SourceFile:
    path: str  # posix path relative to the source folder
    text: str
    content_hash: str


def resolve_location(location: str, repo_root: Path) -> Path:
    path = Path(location)
    return (path if path.is_absolute() else repo_root / path).resolve()


def _matches(rel: str, patterns: tuple[str, ...]) -> bool:
    pure = PurePosixPath(rel)
    for pattern in patterns:
        # "**/x" should also match "x" at the top level
        if pure.match(pattern) or (pattern.startswith("**/") and pure.match(pattern[3:])):
            return True
    return False


def walk(folder: Path, include: tuple[str, ...], exclude: tuple[str, ...]) -> Iterator[SourceFile]:
    if not folder.is_dir():
        raise FileNotFoundError(f"source folder not found: {folder}")
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        rel = path.relative_to(folder).as_posix()
        if include and not _matches(rel, include):
            continue
        if exclude and _matches(rel, exclude):
            continue
        raw = path.read_bytes()
        if len(raw) > MAX_FILE_BYTES or b"\0" in raw[:4096]:
            continue  # large or binary
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        yield SourceFile(rel, text, hashlib.sha256(raw).hexdigest())
