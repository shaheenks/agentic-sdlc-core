"""Source walkers: include/exclude globs, text files and PDFs, stable relative paths.

  local_folder  files under a folder (working tree)
  git           files of a commit (`spec.ref`) in a local repository or an https URL (partial clone
                into a local cache); never the working tree, so a pinned ref is reproducible

Globs match the whole relative path: `*` stays within a directory, `**` spans directories
(`docs/**` = everything under docs/, `**/*.md` = .md files at any depth, including the top level).

Text files (UTF-8, at most 1 MB, no null bytes) carry their text. PDFs (recognised by the `%PDF-`
header, H10) carry their bytes for sdlc_ingest.pdf, up to MAX_PDF_BYTES here; each source's own
`spec.ingest.pdf.max_mb` is enforced by the pipeline, which reports oversized files. Everything else
is skipped.
"""

import hashlib
import re
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

MAX_FILE_BYTES = 1_000_000
MAX_PDF_BYTES = 200 * 1024 * 1024  # hard ceiling (schema maximum of spec.ingest.pdf.max_mb)
PDF = "application/pdf"
TEXT = "text/plain"


@dataclass(frozen=True)
class SourceFile:
    path: str  # posix path relative to the source root (folder or repository)
    text: str  # "" for PDFs (their text comes from sdlc_ingest.pdf)
    content_hash: str
    media_type: str = TEXT
    raw: bytes | None = None  # PDFs only

    @property
    def is_pdf(self) -> bool:
        return self.media_type == PDF


def resolve_location(location: str, repo_root: Path) -> Path:
    path = Path(location)
    return (path if path.is_absolute() else repo_root / path).resolve()


@lru_cache(maxsize=256)
def _glob_regex(pattern: str) -> re.Pattern:
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out))


def _matches(rel: str, patterns: tuple[str, ...]) -> bool:
    return any(_glob_regex(p).fullmatch(rel) for p in patterns)


def _selected(rel: str, include: tuple[str, ...], exclude: tuple[str, ...]) -> bool:
    return (not include or _matches(rel, include)) and not (exclude and _matches(rel, exclude))


def _is_pdf(raw: bytes) -> bool:
    return raw[:1024].lstrip().startswith(b"%PDF-")


def _source_file(rel: str, raw: bytes) -> SourceFile | None:
    """A text file or a PDF; None for anything else (binary, too large, not UTF-8)."""
    digest = hashlib.sha256(raw).hexdigest()
    if _is_pdf(raw):
        return SourceFile(rel, "", digest, PDF, raw) if len(raw) <= MAX_PDF_BYTES else None
    text = _text(raw)
    return SourceFile(rel, text, digest) if text is not None else None


def _too_large(rel: str, size: int) -> bool:
    """Checked before reading: only `.pdf` names may exceed the text limit (the header is
    checked after reading)."""
    limit = MAX_PDF_BYTES if rel.lower().endswith(".pdf") else MAX_FILE_BYTES
    return size > limit


def _text(raw: bytes) -> str | None:
    if len(raw) > MAX_FILE_BYTES or b"\0" in raw[:4096]:
        return None  # large or binary
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def walk(folder: Path, include: tuple[str, ...], exclude: tuple[str, ...]) -> Iterator[SourceFile]:
    if not folder.is_dir():
        raise FileNotFoundError(f"source folder not found: {folder}")
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        rel = path.relative_to(folder).as_posix()
        if not _selected(rel, include, exclude):
            continue
        if _too_large(rel, path.stat().st_size):
            continue
        file = _source_file(rel, path.read_bytes())
        if file is not None:
            yield file


# --- git ------------------------------------------------------------------------------------------


class GitSourceError(RuntimeError):
    pass


def _git(repo: Path, *args: str, stdin: bytes | None = None) -> bytes:
    # safe.directory: the ingest container reads a read-only mount owned by another user
    cmd = ["git", "-c", "safe.directory=*", "-C", str(repo), *args]
    try:
        return subprocess.run(cmd, input=stdin, capture_output=True, check=True).stdout  # noqa: S603
    except subprocess.CalledProcessError as e:
        detail = e.stderr.decode("utf-8", "replace").strip()[:300]
        raise GitSourceError(f"git {' '.join(args[:2])} failed: {detail}") from e
    except FileNotFoundError as e:
        raise GitSourceError("git is not installed") from e


def git_repository(location: str, repo_root: Path, cache_root: Path, ref: str) -> Path:
    """Local repository path, or a partial bare clone of an https URL (cached, ref fetched)."""
    if not location.startswith("https://"):
        path = resolve_location(location, repo_root)
        if not path.exists():
            raise GitSourceError(f"git source not found: {path}")
        return path
    cache = cache_root / hashlib.sha256(location.encode()).hexdigest()[:16]
    if not (cache / "HEAD").is_file():
        cache.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(  # noqa: S603
                ["git", "clone", "--bare", "--filter=blob:none", "--quiet", location, str(cache)],  # noqa: S607
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise GitSourceError(f"git clone failed: {e.stderr.decode()[:300]}") from e
    _git(cache, "fetch", "--quiet", "--filter=blob:none", "origin", ref)
    return cache


def walk_git(
    repo: Path, ref: str, include: tuple[str, ...], exclude: tuple[str, ...]
) -> tuple[str, Iterator[SourceFile]]:
    """(resolved commit, files of that commit) for the selected paths."""
    commit = _git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()
    listing = _git(repo, "ls-tree", "-r", "-z", "-l", commit).split(b"\0")
    wanted = []
    for entry in listing:
        if not entry:
            continue
        meta, _, name = entry.partition(b"\t")
        _mode, kind, _sha, size = meta.split()
        rel = name.decode("utf-8", "replace")
        if kind != b"blob" or size == b"-" or _too_large(rel, int(size)):
            continue
        if _selected(rel, include, exclude):
            wanted.append(rel)
    return commit, _read_blobs(repo, commit, sorted(wanted))


def _read_blobs(repo: Path, commit: str, paths: list[str]) -> Iterator[SourceFile]:
    if not paths:
        return
    request = "".join(f"{commit}:{p}\n" for p in paths).encode()
    out = _git(repo, "cat-file", "--batch", stdin=request)
    pos = 0
    for rel in paths:
        header_end = out.index(b"\n", pos)
        header = out[pos:header_end].split()
        if len(header) < 3 or header[1] != b"blob":
            raise GitSourceError(f"unexpected git object for {rel}: {header!r}")
        size = int(header[2])
        raw = out[header_end + 1 : header_end + 1 + size]
        pos = header_end + 1 + size + 1  # content is followed by a newline
        file = _source_file(rel, raw)
        if file is not None:
            yield file
