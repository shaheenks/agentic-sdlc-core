"""The bundle and pointer documents, and their verification."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

FORMAT = 1


class ConfigUnavailable(Exception):
    """No verified configuration bundle: the caller must refuse the request (NFR-SEC-002)."""


@dataclass(frozen=True)
class Bundle:
    version: str
    env: str
    created_at: str
    git_sha: str
    config: Mapping[str, Any]


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def content_version(env: str, config: Mapping[str, Any]) -> str:
    """The version of a bundle: a hash of its environment and content."""
    return hashlib.sha256(_canonical({"env": env, "config": config})).hexdigest()[:16]


def make_bundle(env: str, config: Mapping[str, Any], git_sha: str = "", now: datetime | None = None) -> dict:
    """The JSON document of a new bundle."""
    return {
        "format": FORMAT,
        "version": content_version(env, config),
        "env": env,
        "created_at": (now or datetime.now(UTC)).isoformat(),
        "git_sha": git_sha,
        "config": config,
    }


def parse_bundle(raw: bytes, version: str | None = None, env: str | None = None) -> Bundle:
    """Load a bundle document and verify it: its content must hash to its version, which must be the one
    expected, for the expected environment."""
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        raise ConfigUnavailable(f"bundle is not JSON: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("format") != FORMAT or not isinstance(doc.get("config"), dict):
        raise ConfigUnavailable("bundle has an unknown format")
    actual = content_version(str(doc.get("env")), doc["config"])
    if doc.get("version") != actual:
        raise ConfigUnavailable(f"bundle content does not match its version {doc.get('version')!r}")
    if version is not None and actual != version:
        raise ConfigUnavailable(f"bundle is version {actual}, expected {version}")
    if env is not None and doc["env"] != env:
        raise ConfigUnavailable(f"bundle {actual} is for environment {doc['env']!r}, not {env!r}")
    return Bundle(actual, doc["env"], str(doc.get("created_at", "")), str(doc.get("git_sha", "")), doc["config"])


def make_pointer(version: str, activated_by: str, previous: str | None, now: datetime | None = None) -> dict:
    """The JSON document of `active.json`."""
    return {
        "version": version,
        "activated_by": activated_by,
        "activated_at": (now or datetime.now(UTC)).isoformat(),
        "previous": previous,
    }


def parse_pointer(raw: bytes) -> dict:
    """The pointer document; its version must be a plain bundle name."""
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        raise ConfigUnavailable(f"active.json is not JSON: {exc}") from exc
    version = doc.get("version") if isinstance(doc, dict) else None
    if not isinstance(version, str) or not version.isalnum():
        raise ConfigUnavailable(f"active.json names an invalid version {version!r}")
    return doc
