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
import os
import re
import shutil
import stat
import subprocess
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from sdlc_loaders.base import PDF, SourceItem

MAX_FILE_BYTES = 1_000_000
MAX_PDF_BYTES = 200 * 1024 * 1024  # hard ceiling (schema maximum of spec.ingest.pdf.max_mb)


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


def _source_file(rel: str, raw: bytes) -> SourceItem | None:
    """A text file or a PDF; None for anything else (binary, too large, not UTF-8)."""
    digest = hashlib.sha256(raw).hexdigest()
    if _is_pdf(raw):
        return SourceItem(rel, "", digest, PDF, raw) if len(raw) <= MAX_PDF_BYTES else None
    text = _text(raw)
    return SourceItem(rel, text, digest) if text is not None else None


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


def walk(folder: Path, include: tuple[str, ...], exclude: tuple[str, ...]) -> Iterator[SourceItem]:
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


FETCHED = "FETCH_HEAD"  # remote repositories are read at the commit the last fetch resolved
# Remote clones are partial: every blob up to the text-file limit comes in the clone/fetch pack
# (one request), larger ones stay on the server. A blob:none clone would fetch each file lazily,
# one request per file, which large repositories (and GitHub) do not tolerate.
CLONE_FILTER = f"blob:limit={MAX_FILE_BYTES}"
NO_LAZY_FETCH = {"GIT_NO_LAZY_FETCH": "1"}  # git >= 2.44: report missing objects, don't fetch


def _git(
    repo: Path, *args: str, stdin: bytes | None = None, env: dict[str, str] | None = None
) -> bytes:
    # safe.directory: the ingest container reads a read-only mount owned by another user
    cmd = ["git", "-c", "safe.directory=*", "-C", str(repo), *args]
    try:
        return subprocess.run(  # noqa: S603
            cmd, input=stdin, capture_output=True, check=True, env=env
        ).stdout
    except subprocess.CalledProcessError as e:
        detail = e.stderr.decode("utf-8", "replace").strip()[:300]
        raise GitSourceError(f"git {' '.join(args[:2])} failed: {detail}") from e
    except FileNotFoundError as e:
        raise GitSourceError("git is not installed") from e


def remote_git_env(location: str, auth_header: str | None = None) -> dict[str, str]:
    """Environment for git talking to an https remote: never prompt, ignore credential helpers,
    and send `auth_header` only to the repository's own host (http.<url>.extraHeader). The token
    travels in the git process environment, never in argv or the URL."""
    parts = urlsplit(location)
    entries = [("credential.helper", "")]  # an empty value clears configured helpers
    if auth_header:
        entries.append((f"http.{parts.scheme}://{parts.netloc}/.extraHeader", auth_header))
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_CONFIG_KEY_")}
    env.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never", GIT_CONFIG_COUNT=str(len(entries)))
    for i, (key, value) in enumerate(entries):
        env[f"GIT_CONFIG_KEY_{i}"], env[f"GIT_CONFIG_VALUE_{i}"] = key, value
    return env


def git_repository(
    location: str, repo_root: Path, cache_root: Path, ref: str, auth_header: str | None = None
) -> Path:
    """Local repository path, or a partial bare clone of an https URL (cached; `ref` fetched, so
    read it at FETCH_HEAD: a tracked branch then always means its current commit)."""
    if not location.startswith("https://"):
        path = resolve_location(location, repo_root)
        if not path.exists():
            raise GitSourceError(f"git source not found: {path}")
        return path
    env = remote_git_env(location, auth_header)
    cache = cache_root / hashlib.sha256(location.encode()).hexdigest()[:16]
    if (cache / "HEAD").is_file() and _clone_filter(cache) != CLONE_FILTER:
        shutil.rmtree(cache, onexc=_make_writable)  # cloned with another filter: clone again
    if not (cache / "HEAD").is_file():
        cache.parent.mkdir(parents=True, exist_ok=True)
        try:
            clone = ["git", "clone", "--bare", f"--filter={CLONE_FILTER}", "--quiet"]
            subprocess.run(  # noqa: S603
                [*clone, location, str(cache)],
                capture_output=True,
                check=True,
                env=env,
            )
        except subprocess.CalledProcessError as e:
            raise GitSourceError(f"git clone failed: {e.stderr.decode()[:300]}") from e
    _git(cache, "fetch", "--quiet", f"--filter={CLONE_FILTER}", "origin", ref, env=env)
    return cache


def _make_writable(func, path, _exc) -> None:
    """rmtree helper: git pack files are read-only (Windows refuses to delete them)."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _clone_filter(repo: Path) -> str | None:
    try:
        return _git(repo, "config", "--get", "remote.origin.partialclonefilter").decode().strip()
    except GitSourceError:
        return None


def resolve_commit(repo: Path, rev: str) -> str:
    return _git(repo, "rev-parse", "--verify", f"{rev}^{{commit}}").decode().strip()


def selected_paths(
    repo: Path, commit: str, include: tuple[str, ...], exclude: tuple[str, ...]
) -> list[str]:
    """Paths of the commit that match the globs and are not too large (sorted). No file content
    is fetched: sizes come from one batch-check of the objects present. In a partial clone an
    absent blob is larger than CLONE_FILTER's limit (= MAX_FILE_BYTES): too large for text,
    still wanted if it is a PDF (fetched when read)."""
    candidates = []
    for entry in _git(repo, "ls-tree", "-r", "-z", commit).split(b"\0"):
        if not entry:
            continue
        meta, _, name = entry.partition(b"\t")
        _mode, kind, sha = meta.split()
        rel = name.decode("utf-8", "replace")
        if kind == b"blob" and _selected(rel, include, exclude):
            candidates.append((rel, sha.decode()))
    sizes = _object_sizes(repo, [sha for _, sha in candidates])
    wanted = []
    for rel, sha in candidates:
        size = sizes.get(sha)
        if size is None and not rel.lower().endswith(".pdf"):
            continue
        if size is not None and _too_large(rel, size):
            continue
        wanted.append(rel)
    return sorted(wanted)


def _object_sizes(repo: Path, shas: list[str]) -> dict[str, int]:
    """Sizes of the objects present locally, in one git call; absent ones are left out."""
    if not shas:
        return {}
    request = "".join(f"{sha}\n" for sha in dict.fromkeys(shas)).encode()
    out = _git(
        repo,
        "cat-file",
        "--batch-check=%(objectname) %(objectsize)",
        stdin=request,
        env={**os.environ, **NO_LAZY_FETCH},
    )
    sizes = {}
    for line in out.decode().splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].isdigit():  # "<sha> missing" otherwise
            sizes[parts[0]] = int(parts[1])
    return sizes


def changed_paths(repo: Path, old: str, new: str) -> set[str] | None:
    """Paths that differ between two commits, or None when `old` is not available (e.g. history
    rewritten): the caller then reads everything."""
    try:
        _git(repo, "cat-file", "-e", f"{old}^{{commit}}")
    except GitSourceError:
        return None
    out = _git(repo, "diff", "--name-only", "--no-renames", "-z", old, new)
    return {p.decode("utf-8", "replace") for p in out.split(b"\0") if p}


def walk_git(
    repo: Path,
    ref: str,
    include: tuple[str, ...],
    exclude: tuple[str, ...],
) -> tuple[str, Iterator[SourceItem]]:
    """(resolved commit, files of that commit) for the selected paths."""
    commit = resolve_commit(repo, ref)
    return commit, read_blobs(repo, commit, selected_paths(repo, commit, include, exclude))


def prefetch_blobs(repo: Path, commit: str, paths: list[str], env: dict[str, str]) -> int:
    """Fetch the blobs of `paths` that a partial clone does not have yet (PDFs above the clone
    limit) in ONE network call with the remote's environment, so reading them later is local and
    never fetches lazily (one request per file, without the token). Returns how many."""
    wanted = set(paths)
    shas = []
    for entry in _git(repo, "ls-tree", "-r", "-z", commit).split(b"\0"):
        meta, _, name = entry.partition(b"\t")
        if entry and name.decode("utf-8", "replace") in wanted:
            shas.append(meta.split()[2].decode())
    present = _object_sizes(repo, shas)
    missing = [sha for sha in dict.fromkeys(shas) if sha not in present]
    if missing:  # --no-write-fetch-head: the branch tip stays in FETCH_HEAD
        fetch = ["fetch", "--quiet", "--no-tags", "--no-write-fetch-head", "--filter=blob:none"]
        _git(repo, *fetch, "origin", *missing, env=env)
    return len(missing)


def read_blobs(repo: Path, commit: str, paths: list[str]) -> Iterator[SourceItem]:
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
