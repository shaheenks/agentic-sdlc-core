"""Load config files → substitute ${VAR} → validate (schema + cross-refs) → Snapshot.

Kinds loaded so far: Platform, GroupMap (Stage 2); RoleSet, ToolCatalog, Team (Stage 3).
Later stages register SkillCatalog (4) and Source (5); files of those kinds are not read yet.
Team `addons` are schema-validated now and resolved in Stage 4.
"""

import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from sdlc_config.errors import ConfigError
from sdlc_config.model import (
    GroupMap,
    IdentityRef,
    PlatformConfig,
    RoleBinding,
    RoleDef,
    Snapshot,
    TeamDef,
    ToolDef,
)

API_VERSION = "sdlc/v1"
_VAR = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")
# Used by `validate --dummy-env` so CI can check structure without real tenant values.
DUMMY_ENV_VALUE = "00000000-0000-0000-0000-000000000000"


@dataclass(frozen=True)
class _Kind:
    schema: str
    path: str  # relative to the config dir; {env} is substituted; a glob if `many`
    many: bool = False  # several files of this kind (e.g. teams/*.yaml); zero is allowed


_KINDS: dict[str, _Kind] = {
    "Platform": _Kind("platform.schema.json", "platform.yaml"),
    "GroupMap": _Kind("groupmap.schema.json", "env/{env}/groups.yaml"),
    "RoleSet": _Kind("roleset.schema.json", "roles.yaml"),
    "ToolCatalog": _Kind("toolcatalog.schema.json", "tools.yaml"),
    "Team": _Kind("team.schema.json", "teams/*.yaml", many=True),
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
    docs: dict[str, list[tuple[str, dict]]] = {}

    for kind, spec in _KINDS.items():
        schema_path = config_dir / "schemas" / spec.schema
        if not schema_path.is_file():
            problems.append(f"schemas/{spec.schema}: schema not found")
            continue
        raw_files[f"schemas/{spec.schema}"] = schema_path.read_bytes()
        schema = json.loads(raw_files[f"schemas/{spec.schema}"])
        pattern = spec.path.format(env=env)
        if spec.many:
            paths = sorted(config_dir.glob(pattern))
        else:
            path = config_dir / pattern
            if not path.is_file():
                hint = ""
                if path.with_name(path.name + ".example").is_file():
                    hint = f" (copy {pattern}.example to {pattern} and fill in tenant values)"
                problems.append(f"{pattern}: file not found{hint}")
                continue
            paths = [path]
        docs[kind] = []
        for path in paths:
            rel = path.relative_to(config_dir).as_posix()
            doc = _read_doc(path, rel, kind, schema, environ, dummy_env, raw_files, problems)
            if doc is not None:
                docs[kind].append((rel, doc))

    if problems:
        raise ConfigError(problems)

    platform = _build_platform(docs["Platform"][0][1], problems)
    groups = _build_groups(docs["GroupMap"][0][1], env, problems)
    aliases = set(groups.alias_by_id.values())
    tools = _build_tools(docs["ToolCatalog"][0][1], problems)
    roles, bindings = _build_roles(docs["RoleSet"][0][1], tools, aliases, platform, problems)
    teams = _build_teams(docs["Team"], roles, tools, aliases, problems)
    if problems:
        raise ConfigError(problems)

    return Snapshot(
        version=_version(raw_files, environ),
        env=env,
        loaded_at=datetime.now(UTC),
        platform=platform,
        groups=groups,
        roles=MappingProxyType(roles),
        bindings=bindings,
        tools=MappingProxyType(tools),
        teams=MappingProxyType(teams),
    )


def _read_doc(path, rel, kind, schema, environ, dummy_env, raw_files, problems) -> dict | None:
    raw = path.read_bytes()
    raw_files[rel] = raw
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        problems.append(f"{rel}: invalid YAML: {e}")
        return None
    if not isinstance(doc, dict):
        problems.append(f"{rel}: expected a mapping at top level")
        return None
    if doc.get("kind") != kind:
        problems.append(f"{rel}: expected kind '{kind}', got {doc.get('kind')!r}")
        return None
    doc = _substitute(doc, environ, dummy_env, rel, problems)
    for err in sorted(Draft202012Validator(schema).iter_errors(doc), key=lambda e: e.path):
        where = "/".join(str(p) for p in err.absolute_path) or "(root)"
        problems.append(f"{rel}: {where}: {err.message}")
    return doc


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


# --- Platform / GroupMap (Stage 2) ------------------------------------------------------------


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


# --- ToolCatalog / RoleSet / Team (Stage 3) ---------------------------------------------------


def _build_tools(doc: dict, problems: list[str]) -> dict[str, ToolDef]:
    servers = set(doc["servers"])
    tools = {}
    for name, entry in doc["tools"].items():
        if entry["server"] not in servers:
            problems.append(f"tools.yaml: tools/{name}: unknown server '{entry['server']}'")
        tools[name] = ToolDef(
            name=name,
            server=entry["server"],
            risk=entry["risk"],
            data_scoped=entry.get("data_scoped", False),
            args=frozenset(entry.get("args", {})),
        )
    return tools


EVERYONE = IdentityRef("everyone", "*")


def _identity(entry: dict) -> IdentityRef:
    if entry.get("everyone"):
        return EVERYONE
    if "group" in entry:
        return IdentityRef("group", entry["group"])
    return IdentityRef("app_role", entry["app_role"])


def _check_binding(ref: IdentityRef, roles, rel: str, where: str, aliases, known_roles, problems):
    if ref.kind == "group" and ref.value not in aliases:
        problems.append(f"{rel}: {where}: unknown group alias '{ref.value}' (not in groups.yaml)")
    for role in roles:
        if role not in known_roles:
            problems.append(f"{rel}: {where}: unknown role '{role}'")


def _check_tools(names, rel: str, where: str, tools, problems, allow_wildcard: bool):
    for name in names:
        if name == "*" and allow_wildcard:
            continue
        if name not in tools:
            problems.append(f"{rel}: {where}: unknown tool '{name}' (not in tools.yaml)")


def _build_roles(doc, tools, aliases, platform, problems):
    rel = "roles.yaml"
    known = set(doc["roles"])
    roles = {}
    for name, entry in doc["roles"].items():
        tool_rules = entry.get("tools", {})
        allow, deny = tool_rules.get("allow", []), tool_rules.get("deny", [])
        _check_tools(allow, rel, f"roles/{name}/tools/allow", tools, problems, True)
        _check_tools(deny, rel, f"roles/{name}/tools/deny", tools, problems, False)
        for parent in entry.get("inherits", []):
            if parent not in known:
                problems.append(f"{rel}: roles/{name}/inherits: unknown role '{parent}'")
        level = entry.get("data", {}).get("max_classification")
        if level is not None and level not in platform.classification_levels:
            problems.append(f"{rel}: roles/{name}/data/max_classification: unknown '{level}'")
        roles[name] = RoleDef(
            name=name,
            inherits=tuple(entry.get("inherits", [])),
            tools_allow=frozenset(allow),
            tools_deny=frozenset(deny),
            unconstrained=tool_rules.get("unconstrained", False),
        )
    for cycle in _inheritance_cycles(roles):
        problems.append(f"{rel}: role inheritance cycle: {' -> '.join(cycle)}")

    bindings = []
    for i, entry in enumerate(doc.get("bindings", [])):
        ref, where = _identity(entry), f"bindings[{i}]"
        _check_binding(ref, entry["roles"], rel, where, aliases, known, problems)
        bindings.append(RoleBinding(ref, tuple(entry["roles"]), f"{rel}#{where}"))
    return roles, tuple(bindings)


def _inheritance_cycles(roles: dict[str, RoleDef]) -> list[list[str]]:
    cycles, state = [], {}  # state: 1 = visiting, 2 = done

    def visit(name: str, path: list[str]) -> None:
        if state.get(name) == 2 or name not in roles:
            return
        if state.get(name) == 1:
            cycles.append(path[path.index(name) :] + [name])
            return
        state[name] = 1
        for parent in roles[name].inherits:
            visit(parent, path + [name])
        state[name] = 2

    for name in roles:
        visit(name, [])
    return cycles


def _build_teams(team_docs, roles, tools, aliases, problems) -> dict[str, TeamDef]:
    teams: dict[str, TeamDef] = {}
    for rel, doc in team_docs:
        name = doc["metadata"]["name"]
        if name != Path(rel).stem:
            problems.append(f"{rel}: metadata/name '{name}' must match the file name")
        if name in teams:
            problems.append(f"{rel}: duplicate team '{name}' (also in {teams[name].source})")
            continue
        for owner in doc["metadata"].get("owners", []):
            if owner not in aliases:
                problems.append(f"{rel}: metadata/owners: unknown group alias '{owner}'")
        membership = []
        for i, entry in enumerate(doc["membership"]):
            ref, where = _identity(entry), f"membership[{i}]"
            _check_binding(ref, entry["roles"], rel, where, aliases, roles, problems)
            membership.append(RoleBinding(ref, tuple(entry["roles"]), f"{rel}#{where}", name))
        tool_policy = doc.get("policy", {}).get("tools", {})
        deny = tool_policy.get("deny", [])
        _check_tools(deny, rel, "policy/tools/deny", tools, problems, False)
        constraints = {}
        for tool, rule in tool_policy.get("constraints", {}).items():
            if tool not in tools:
                problems.append(f"{rel}: policy/tools/constraints: unknown tool '{tool}'")
                continue
            for arg in rule["args"]:
                if arg not in tools[tool].args:
                    problems.append(
                        f"{rel}: policy/tools/constraints/{tool}: argument '{arg}' is not "
                        f"declared for the tool in tools.yaml"
                    )
            constraints[tool] = MappingProxyType(
                {arg: frozenset(spec["in"]) for arg, spec in rule["args"].items()}
            )
        teams[name] = TeamDef(
            name=name,
            source=rel,
            owners=tuple(doc["metadata"].get("owners", [])),
            membership=tuple(membership),
            tools_deny=frozenset(deny),
            constraints=MappingProxyType(constraints),
        )
    return teams


def _version(raw_files: dict[str, bytes], environ: Mapping[str, str]) -> str:
    """<git sha or 'local'>-<hash of config file bytes>. Env values are not part of it."""
    digest = hashlib.sha256()
    for rel in sorted(raw_files):
        digest.update(rel.encode() + b"\0" + raw_files[rel] + b"\0")
    git_sha = environ.get("SDLC_CONFIG_GIT_SHA", "")[:12] or "local"
    return f"{git_sha}-{digest.hexdigest()[:12]}"
