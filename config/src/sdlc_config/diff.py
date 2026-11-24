"""Who gains or loses which tools and knowledge sources between two configuration versions (FR-CFG-002).

Access is computed with the Access Policy itself (`sdlc_policy.effective_policy`), so the diff shows what the
MCP servers would decide, for every listed user, in their own runs and in each of their teams' runs, on every
surface; a readable knowledge source shows as `source:<id>`. Users not listed in `users.yaml` are one more
row: they are in no team and no user group, so they get only what is granted to everyone. A user blocked by
email gets nothing.

A version is one of:

- a configuration folder, compiled for the environment (default: the working tree);
- `git:<ref>`: the configuration at a git revision. Environment folders other than `example` are git-ignored,
  so they are taken from the working tree;
- `<folder or gs://bucket[/prefix]>@<version>` or `...@active`: a published bundle.
"""

import io
import shutil
import subprocess
import tempfile
import zipfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sdlc_config_store import ConfigUnavailable, parse_bundle, parse_pointer, source_from_url
from sdlc_config_store.sources import bundle_name
from sdlc_directory import Memberships, memberships
from sdlc_policy import effective_policy

from sdlc_config.compile import compile_config

UNLISTED = "(users not listed)"
OWN = "own runs"
GIT = "git:"
ACTIVE = "active"
SOURCE = "source:"


class VersionUnavailable(Exception):
    """A version could not be read or does not compile."""


@dataclass(frozen=True)
class Change:
    user: str
    context: str  # "own runs" or "<team> runs"
    surface: str
    gained: tuple[str, ...]
    lost: tuple[str, ...]


def _blocked_emails(config: Mapping[str, Any]) -> set[str]:
    return {str(b["email"]).lower() for b in config.get("blocked") or () if b.get("email")}


def access(config: Mapping[str, Any]) -> dict[tuple[str, str, str], frozenset[str]]:
    """(user, context, surface) -> the tools and `source:<id>` allowed there. Empty rows are left out."""
    blocked = _blocked_emails(config)
    users: dict[str, Memberships] = {UNLISTED: Memberships()}
    for email in config.get("members") or {}:
        users[email] = memberships(config, email)
    result: dict[tuple[str, str, str], frozenset[str]] = {}
    for user, member in users.items():
        if user in blocked:  # refused before any policy applies
            continue
        contexts: list[tuple[str, str | None]] = [(OWN, None)] + [(f"{t} runs", t) for t in sorted(member.teams)]
        for surface in config.get("surfaces") or {}:
            for label, team in contexts:
                policy = effective_policy(config, "", surface, member, team)
                allowed = frozenset(policy.tools) | {f"{SOURCE}{s}" for s in policy.sources}
                if allowed:
                    result[(user, label, surface)] = allowed
    return result


def diff(old: Mapping[str, Any], new: Mapping[str, Any]) -> list[Change]:
    before, after = access(old), access(new)
    changes = []
    for key in sorted(before.keys() | after.keys(), key=lambda k: (k[0] == UNLISTED, k)):
        was, now = before.get(key, frozenset()), after.get(key, frozenset())
        if was != now:
            changes.append(Change(*key, gained=tuple(sorted(now - was)), lost=tuple(sorted(was - now))))
    return changes


def render(changes: list[Change], env: str, base: str, head: str) -> str:
    lines = [f"Permission diff for env {env}: {base} -> {head}", ""]
    if not changes:
        lines.append("No one gains or loses a tool or knowledge source.")
        return "\n".join(lines) + "\n"
    user = None
    for change in changes:
        if change.user != user:
            user = change.user
            lines.append(user)
        parts = [
            f"+ {', '.join(change.gained)}" if change.gained else "",
            f"- {', '.join(change.lost)}" if change.lost else "",
        ]
        lines.append(f"  {change.context}, {change.surface}: {'; '.join(p for p in parts if p)}")
    lines += ["", "Tools and knowledge sources only: workflows and skills are not declared in configuration yet."]
    return "\n".join(lines) + "\n"


def _git(cwd: Path, *args: str) -> bytes:
    try:
        return subprocess.run(["git", *args], capture_output=True, check=True, cwd=cwd).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", b"") or b""
        raise VersionUnavailable(f"git {' '.join(args)}: {detail.decode(errors='replace').strip() or exc}") from exc


@contextmanager
def _git_checkout(ref: str, config_dir: Path, env: str) -> Iterator[Path]:
    """The configuration folder as of `ref`, in a temporary folder, with the working tree's env folder when git
    has none for it."""
    top = Path(_git(config_dir, "rev-parse", "--show-toplevel").decode().strip())
    relative = config_dir.resolve().relative_to(top.resolve()).as_posix()
    archive = _git(top, "archive", "--format=zip", ref, relative)
    with tempfile.TemporaryDirectory() as tmp:
        zipfile.ZipFile(io.BytesIO(archive)).extractall(tmp)
        root = Path(tmp) / relative
        env_dir, working_env = root / "env" / env, config_dir / "env" / env
        if not env_dir.exists() and working_env.is_dir():
            shutil.copytree(working_env, env_dir)
        yield root


def _compiled(config_dir: Path, env: str, what: str) -> dict[str, Any]:
    try:
        compiled = compile_config(config_dir, env)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:  # files in a shape this compiler predates
        raise VersionUnavailable(f"{what} cannot be compiled by this version of sdlc-config: {exc!r}") from exc
    if not compiled.ok:
        raise VersionUnavailable(f"{what} does not compile: {'; '.join(compiled.problems)}")
    return compiled.config


def load(version: str, env: str, config_dir: Path) -> dict[str, Any]:
    """The compiled configuration of one version (see the module docstring for the forms)."""
    if version.startswith(GIT):
        with _git_checkout(version[len(GIT) :], config_dir, env) as root:
            return _compiled(root, env, version)
    location, at, name = version.rpartition("@")
    if at and location:
        source = source_from_url(location)
        try:
            if name == ACTIVE:
                name = parse_pointer(source.read_active()[0])["version"]
            return dict(parse_bundle(source.read(bundle_name(name)), name, env).config)
        except (OSError, ConfigUnavailable) as exc:
            raise VersionUnavailable(f"{version}: {exc}") from exc
    return _compiled(Path(version), env, version)
