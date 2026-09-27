"""Immutable config bundles with a `current` pointer (Stage 7b, local folder store).

Layout under a bundle root:

  <root>/current                 text file: the active bundle version (rollback = point back)
  <root>/<version>/manifest.json version, env, git_sha, created_at, files {path: sha256}
  <root>/<version>/tree/...      exactly the files the loader read: config/... and skills/...

A bundle is compiled from a validated config folder and never changes afterwards: its version is
`<git sha>-<hash of every file>`, so different content always means a different directory.
Files are copied as they are in git, so `${VAR}` placeholders stay unresolved (bundles never
contain secrets); values are resolved from the environment when the bundle is loaded.
The tenant's groups.yaml IS included (group IDs, not secrets): keep bundle roots out of git.
Loading verifies every file against the manifest and the recomputed version before serving.
A GCS store (7b on GCP) uses the same layout and pointer.
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from sdlc_config.errors import ConfigError
from sdlc_config.loader import load_snapshot
from sdlc_config.model import Snapshot

POINTER = "current"
MANIFEST = "manifest.json"
TREE = "tree"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_sha(repo_root: Path) -> str:
    """Short HEAD SHA of the repo holding the config, or '' outside git."""
    try:
        out = subprocess.run(  # noqa: S603 - fixed argv
            ["git", "-C", str(repo_root), "rev-parse", "--short=12", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return out.stdout.strip()


def compile_bundle(
    config_dir: Path,
    env: str,
    out_root: Path,
    environ: Mapping[str, str] | None = None,
    dummy_env: bool = False,
) -> tuple[str, bool]:
    """Validate config_dir for env and write an immutable bundle. Returns (version, created);
    created is False if that exact bundle already exists."""
    environ = dict(os.environ if environ is None else environ)
    sha = environ.get("SDLC_CONFIG_GIT_SHA") or git_sha(config_dir.parent)
    environ["SDLC_CONFIG_GIT_SHA"] = sha
    snapshot = load_snapshot(config_dir, env, environ, dummy_env=dummy_env)  # raises ConfigError
    target = out_root / snapshot.version
    if (target / MANIFEST).is_file():
        return snapshot.version, False

    out_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{snapshot.version}-", dir=out_root))
    try:
        for rel, digest in snapshot.files.items():
            source = _source_path(config_dir, rel)
            if _sha256(source) != digest:  # changed while compiling
                raise ConfigError([f"{rel}: changed during compile; run compile again"])
            dest = staging / TREE / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
        manifest = {
            "version": snapshot.version,
            "env": env,
            "git_sha": sha,
            "created_at": datetime.now(UTC).isoformat(),
            "files": dict(sorted(snapshot.files.items())),
        }
        (staging / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        staging.rename(target)  # atomic publish: a bundle directory is complete or absent
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return snapshot.version, True


def _source_path(config_dir: Path, rel: str) -> Path:
    """Bundle paths are repo-relative: config/<...> maps to config_dir, the rest (skills/...)
    to the repo root (config_dir's parent)."""
    if rel.startswith("config/"):
        return config_dir / rel.removeprefix("config/")
    return config_dir.parent / rel


def list_bundles(root: Path) -> list[dict]:
    """Manifests of all bundles under root, oldest first."""
    manifests = []
    for manifest in root.glob(f"*/{MANIFEST}"):
        try:
            manifests.append(json.loads(manifest.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(manifests, key=lambda m: m.get("created_at", ""))


def current_version(root: Path) -> str:
    pointer = root / POINTER
    if not pointer.is_file():
        raise ConfigError([f"{pointer}: no active bundle (run sdlc-config compile --activate)"])
    version = pointer.read_text(encoding="utf-8").strip()
    if not version or "/" in version or "\\" in version or version.startswith("."):
        raise ConfigError([f"{pointer}: invalid bundle version {version!r}"])
    return version


def activate(root: Path, version: str, env: str | None = None) -> None:
    """Point `current` at a bundle (atomic replace). Rollback = activate an older version.
    The bundle is fully verified first, so the pointer never moves to a broken bundle."""
    manifest = verify_bundle(root, version)
    if env is not None and manifest["env"] != env:
        raise ConfigError([f"bundle {version} is for env '{manifest['env']}', not '{env}'"])
    tmp = root / f".{POINTER}.tmp"
    tmp.write_text(version + "\n", encoding="utf-8")
    os.replace(tmp, root / POINTER)


def verify_bundle(root: Path, version: str) -> dict:
    """Manifest of a bundle whose files all match their recorded hashes (and nothing else)."""
    bundle = root / version
    try:
        manifest = json.loads((bundle / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ConfigError([f"bundle {version}: unreadable manifest ({e})"]) from e
    problems = []
    if manifest.get("version") != version:
        problems.append(f"bundle {version}: manifest names version {manifest.get('version')!r}")
    files: dict[str, str] = manifest.get("files", {})
    tree = bundle / TREE
    present = {p.relative_to(tree).as_posix() for p in tree.rglob("*") if p.is_file()}
    for rel in sorted(present - set(files)):
        problems.append(f"bundle {version}: unexpected file {rel}")
    for rel, digest in files.items():
        path = tree / rel
        if not path.is_file():
            problems.append(f"bundle {version}: missing file {rel}")
        elif _sha256(path) != digest:
            problems.append(f"bundle {version}: {rel} does not match the manifest")
    if problems:
        raise ConfigError(problems)
    return manifest


def load_bundle(
    root: Path, env: str, version: str | None = None, environ: Mapping[str, str] | None = None
) -> Snapshot:
    """Load the active (or given) bundle: verify files, load, and check the version matches."""
    version = version or current_version(root)
    manifest = verify_bundle(root, version)
    if manifest["env"] != env:
        raise ConfigError([f"bundle {version} is for env '{manifest['env']}', not '{env}'"])
    environ = dict(os.environ if environ is None else environ)
    environ["SDLC_CONFIG_GIT_SHA"] = manifest["git_sha"]
    snapshot = load_snapshot(root / version / TREE / "config", env, environ)
    if snapshot.version != version:
        raise ConfigError([f"bundle {version}: content loads as version {snapshot.version}"])
    return snapshot
