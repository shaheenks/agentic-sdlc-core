"""Reading a source's files: a folder under the ingest root, a `gs://` prefix, or a git repository (DEC-0011).

Only text files are kept (UTF-8, no NUL bytes, at most `MAX_FILE_BYTES`), filtered by the source's include
and exclude patterns. A pattern without `/` matches a file name anywhere; `**` matches any number of folders."""

import base64
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

MAX_FILE_BYTES = 512 * 1024
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build", ".terraform"}
SHA = re.compile(r"^[0-9a-f]{40}$")


class FetchError(Exception):
    """A source could not be read; the message never contains a credential."""


@dataclass
class Fetched:
    files: dict[str, str] = field(default_factory=dict)  # posix path inside the source -> text
    revision: str = ""  # git commit, when there is one
    skipped: int = 0  # not text, too large, or excluded


def _glob(pattern: str) -> re.Pattern:
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(f"^{out}$")


def selector(include: Iterable[str] | None, exclude: Iterable[str] | None) -> Callable[[str], bool]:
    def compiled(patterns):
        return [(p, _glob(p)) for p in patterns or ()]

    inc, exc = compiled(include), compiled(exclude)

    def hit(path: str, patterns) -> bool:
        name = PurePosixPath(path).name
        return any(rx.match(name if "/" not in p else path) for p, rx in patterns)

    return lambda path: (not inc or hit(path, inc)) and not hit(path, exc)


def as_text(data: bytes) -> str | None:
    if len(data) > MAX_FILE_BYTES or b"\x00" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _walk(root: Path, wanted: Callable[[str], bool]) -> Fetched:
    fetched = Fetched()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            if not wanted(rel) or path.is_symlink():
                fetched.skipped += 1
                continue
            text = as_text(path.read_bytes()) if path.stat().st_size <= MAX_FILE_BYTES else None
            if text is None:
                fetched.skipped += 1
            else:
                fetched.files[rel] = text
    return fetched


def fetch_folder(source: Mapping[str, Any], root: Path, gcs_client=None) -> Fetched:
    wanted = selector(source.get("include"), source.get("exclude"))
    location = source["location"]
    if location.startswith("gs://"):
        return _fetch_gcs(location, wanted, gcs_client)
    base = (root / location).resolve()
    if not base.is_relative_to(root.resolve()):
        raise FetchError("folder is outside the ingest root")
    if not base.is_dir():
        raise FetchError(f"folder {location!r} not found under the ingest root")
    return _walk(base, wanted)


def _fetch_gcs(location: str, wanted: Callable[[str], bool], client=None) -> Fetched:
    from google.cloud import storage

    bucket_name, _, prefix = location[5:].partition("/")
    prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""
    client = client or storage.Client()
    fetched = Fetched()
    for blob in client.list_blobs(bucket_name, prefix=prefix):
        rel = blob.name[len(prefix) :]
        if not rel or rel.endswith("/"):
            continue
        if not wanted(rel) or (blob.size or 0) > MAX_FILE_BYTES:
            fetched.skipped += 1
            continue
        text = as_text(blob.download_as_bytes())
        if text is None:
            fetched.skipped += 1
        else:
            fetched.files[rel] = text
    return fetched


def _git(args: list[str], cwd: Path, env: Mapping[str, str]) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, env={**os.environ, **env}, capture_output=True, text=True)
    if result.returncode != 0:
        # git prints the URL, never the header; keep only the last line, which says what failed.
        lines = [line for line in result.stderr.strip().splitlines() if line.strip()]
        raise FetchError(f"git {args[0]} failed: {lines[-1] if lines else result.returncode}")
    return result.stdout.strip()


def default_username(location: str) -> str:
    """The Basic username a host's read token signs in with (DEC-0014): Bitbucket Cloud access tokens use
    `x-token-auth`; GitHub, and any other host unless the source names one, `x-access-token`."""
    host = urlsplit(location).hostname or ""
    return "x-token-auth" if host == "bitbucket.org" else "x-access-token"


def authorization(source: Mapping[str, Any], token: str) -> str:
    """The HTTP Authorization header for a git source's read token: Basic with the declared or the host's default
    username, or Bearer (Bitbucket Data Center HTTP access tokens) (DEC-0014)."""
    if source.get("credential_scheme") == "bearer":
        return f"Authorization: Bearer {token}"
    username = source.get("credential_username") or default_username(source["location"])
    return "Authorization: Basic " + base64.b64encode(f"{username}:{token}".encode()).decode()


def fetch_git(source: Mapping[str, Any], read_secret: Callable[[str], str], workdir: Path | None = None) -> Fetched:
    """A shallow clone of the source's ref. A read token goes in an HTTP header passed through git's
    environment, so it never appears in a command line, a URL or the clone's configuration."""
    env = {"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"}
    if source.get("credential"):
        env |= {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": authorization(source, read_secret(source["credential"])),
        }
    ref = source.get("ref") or ""
    with tempfile.TemporaryDirectory(dir=workdir) as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        _git(["init", "-q"], repo, env)
        _git(["remote", "add", "origin", source["location"]], repo, env)
        _git(["fetch", "-q", "--depth", "1", "origin", ref or "HEAD"], repo, env)
        _git(["checkout", "-q", "FETCH_HEAD"], repo, env)
        revision = _git(["rev-parse", "HEAD"], repo, env)
        fetched = _walk(repo, selector(source.get("include"), source.get("exclude")))
        fetched.revision = revision
        return fetched


def read_secret_from(environ: Mapping[str, str], project: str | None, client=None) -> Callable[[str], str]:
    """A secret's latest version: `INGEST_SECRET_<NAME>` in the environment (local runs), else Secret Manager
    in `project`, with the ingest service account's credentials."""

    def read(name: str) -> str:
        override = environ.get("INGEST_SECRET_" + re.sub(r"[^A-Za-z0-9]", "_", name).upper())
        if override:
            return override.strip()
        if not project:
            raise FetchError(f"secret {name!r}: no GOOGLE_CLOUD_PROJECT to read it from")
        import google.auth
        import google.auth.transport.requests
        import httpx

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        credentials.refresh(google.auth.transport.requests.Request())
        url = f"https://secretmanager.googleapis.com/v1/projects/{project}/secrets/{name}/versions/latest:access"
        http = client or httpx.Client(timeout=10)
        response = http.get(url, headers={"Authorization": f"Bearer {credentials.token}"})
        if response.status_code != 200:
            raise FetchError(f"secret {name!r}: Secret Manager answered {response.status_code}")
        return base64.b64decode(response.json()["payload"]["data"]).decode().strip()

    return read


def link_for(source: Mapping[str, Any], path: str, revision: str) -> str:
    """Where a person can open the file: the source's `link` template, a GitHub page for a GitHub
    repository, or else the path itself."""
    template = source.get("link")
    if template:
        return template.replace("{path}", path).replace("{ref}", revision or source.get("ref") or "HEAD")
    location = source["location"]
    if source["kind"] == "git" and location.startswith("https://github.com/"):
        base = location.removesuffix("/").removesuffix(".git")
        return f"{base}/blob/{revision or source.get('ref') or 'HEAD'}/{path}"
    return path
