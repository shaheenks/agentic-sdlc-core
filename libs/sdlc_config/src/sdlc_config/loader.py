"""Load config files → substitute ${VAR} → validate (schema + cross-refs) → Snapshot.

Stage 2 loads kinds Platform and GroupMap only. Later stages register more kinds here
(RoleSet, ToolCatalog, Team, SkillCatalog, Source); files of those kinds are not read yet.
"""

import hashlib
import json
import os
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from sdlc_config.errors import ConfigError
from sdlc_config.model import GroupMap, PlatformConfig, Snapshot

API_VERSION = "sdlc/v1"
_VAR = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")
# Used by `validate --dummy-env` so CI can check structure without real tenant values.
DUMMY_ENV_VALUE = "00000000-0000-0000-0000-000000000000"

# kind -> (schema file, path relative to config dir; {env} is substituted)
_KINDS: dict[str, tuple[str, str]] = {
    "Platform": ("platform.schema.json", "platform.yaml"),
    "GroupMap": ("groupmap.schema.json", "env/{env}/groups.yaml"),
}


def load_snapshot(
    config_dir: Path,
    env: str,
    environ: Mapping[str, str] | None = None,
    dummy_env: bool = False,
) -> Snapshot:
    """Load and validate config for one environment. Raises ConfigError listing all problems."""
    environ = os.environ if environ is None else environ
    problems: list[str] = []
    raw_files: dict[str, bytes] = {}
    docs: dict[str, Any] = {}

    for kind, (schema_name, rel_template) in _KINDS.items():
        rel = rel_template.format(env=env)
        path = config_dir / rel
        schema_path = config_dir / "schemas" / schema_name
        if not path.is_file():
            hint = ""
            if path.with_name(path.name + ".example").is_file():
                hint = f" (copy {rel}.example to {rel} and fill in your tenant's values)"
            problems.append(f"{rel}: file not found{hint}")
            continue
        if not schema_path.is_file():
            problems.append(f"schemas/{schema_name}: schema not found")
            continue
        raw = path.read_bytes()
        raw_files[rel] = raw
        raw_files[f"schemas/{schema_name}"] = schema_path.read_bytes()
        try:
            doc = yaml.safe_load(raw)
        except yaml.YAMLError as e:
            problems.append(f"{rel}: invalid YAML: {e}")
            continue
        if not isinstance(doc, dict):
            problems.append(f"{rel}: expected a mapping at top level")
            continue
        if doc.get("kind") != kind:
            problems.append(f"{rel}: expected kind '{kind}', got {doc.get('kind')!r}")
            continue
        doc = _substitute(doc, environ, dummy_env, rel, problems)
        schema = json.loads(raw_files[f"schemas/{schema_name}"])
        for err in sorted(Draft202012Validator(schema).iter_errors(doc), key=lambda e: e.path):
            where = "/".join(str(p) for p in err.absolute_path) or "(root)"
            problems.append(f"{rel}: {where}: {err.message}")
        docs[kind] = doc

    if problems:
        raise ConfigError(problems)

    platform = _build_platform(docs["Platform"], problems)
    groups = _build_groups(docs["GroupMap"], env, problems)
    if problems:
        raise ConfigError(problems)

    return Snapshot(
        version=_version(raw_files, environ),
        env=env,
        loaded_at=datetime.now(UTC),
        platform=platform,
        groups=groups,
    )


def _substitute(node: Any, environ: Mapping[str, str], dummy: bool, rel: str, problems: list):
    """Replace ${VAR} in every string. Missing/empty vars are errors (fail closed)."""
    if isinstance(node, dict):
        return {k: _substitute(v, environ, dummy, rel, problems) for k, v in node.items()}
    if isinstance(node, list):
        return [_substitute(v, environ, dummy, rel, problems) for v in node]
    if isinstance(node, str):

        def repl(m: re.Match) -> str:
            value = environ.get(m.group(1), "")
            if value:
                return value
            if dummy:
                return DUMMY_ENV_VALUE
            problems.append(f"{rel}: environment variable {m.group(1)} is not set")
            return m.group(0)

        return _VAR.sub(repl, node)
    return node


def _build_platform(doc: dict, problems: list[str]) -> PlatformConfig:
    ident, levels = doc["identity"], tuple(doc["classification_levels"])
    default_max = doc["defaults"]["max_classification"]
    if default_max not in levels:
        problems.append(
            f"platform.yaml: defaults/max_classification '{default_max}' is not one of {levels}"
        )
    tid = ident["tenant_id"]
    for field in ("issuer", "jwks_uri"):
        if tid not in ident[field]:
            problems.append(f"platform.yaml: identity/{field} does not contain tenant_id")
    return PlatformConfig(
        tenant_id=tid,
        issuer=ident["issuer"],
        jwks_uri=ident["jwks_uri"],
        audience=tuple(ident["audience"]),
        required_scopes=tuple(ident["required_scopes"]),
        groups_overage_fallback=ident["groups"]["overage_fallback"],
        groups_cache_ttl_seconds=ident["groups"]["cache_ttl_seconds"],
        classification_levels=levels,
        default_max_classification=default_max,
    )


def _build_groups(doc: dict, env: str, problems: list[str]) -> GroupMap:
    alias_by_id: dict[str, str] = {}
    for alias, entry in doc["groups"].items():
        gid = entry["id"].lower()
        if gid in alias_by_id:
            problems.append(
                f"env/{env}/groups.yaml: group id {gid} is mapped by both "
                f"'{alias_by_id[gid]}' and '{alias}'"
            )
        alias_by_id[gid] = alias
    return GroupMap(alias_by_id=MappingProxyType(alias_by_id))


def _version(raw_files: dict[str, bytes], environ: Mapping[str, str]) -> str:
    """<git sha or 'local'>-<hash of config file bytes>. Env values are not part of it."""
    digest = hashlib.sha256()
    for rel in sorted(raw_files):
        digest.update(rel.encode() + b"\0" + raw_files[rel] + b"\0")
    git_sha = environ.get("SDLC_CONFIG_GIT_SHA", "")[:12] or "local"
    return f"{git_sha}-{digest.hexdigest()[:12]}"
