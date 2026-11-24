"""YAML files to one compiled, cross-checked configuration."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

SHARED_KINDS = ("platform", "tool_groups", "surfaces", "teams", "user_groups", "grants", "limits", "providers")
ENV_KINDS = ("identity", "users", "blocked")
LOCAL_ONLY_MODES = ("trusted_header",)
UNCONFIGURED = {"mode": "", "allowed_domains": [], "callers": {}, "clients": {}}


@dataclass
class Compiled:
    config: dict[str, Any]
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def _load(path: Path, kind: str, schemas: Path, problems: list[str]) -> dict | None:
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        problems.append(f"{path.name}: invalid YAML: {exc}")
        return None
    schema = json.loads((schemas / f"{kind}.schema.json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(doc), key=lambda e: list(e.absolute_path))
    for error in errors:
        where = "/".join(str(p) for p in error.absolute_path) or "(top)"
        problems.append(f"{path.as_posix()}: {where}: {error.message}")
    return None if errors else doc


def compile_config(config_dir: Path, env: str) -> Compiled:
    problems: list[str] = []
    warnings: list[str] = []
    schemas = config_dir / "schemas"
    docs: dict[str, dict] = {}
    for kind in SHARED_KINDS:
        path = config_dir / f"{kind}.yaml"
        if not path.is_file():
            problems.append(f"{kind}.yaml: missing")
            continue
        doc = _load(path, kind, schemas, problems)
        if doc is not None:
            docs[kind] = doc
    env_dir = config_dir / "env" / env
    if not env_dir.is_dir():
        warnings.append(f"env/{env}/: missing; services will refuse every user in this environment")
    for kind in ENV_KINDS:
        path = env_dir / f"{kind}.yaml"
        if path.is_file():
            doc = _load(path, kind, schemas, problems)
            if doc is not None:
                docs[f"env.{kind}"] = doc
    if problems:
        return Compiled({}, problems, warnings)

    identity = {**UNCONFIGURED, **(docs.get("env.identity") or {})}
    users = (docs.get("env.users") or {}).get("users") or {}
    config: dict[str, Any] = {
        "platform": {k: v for k, v in docs["platform"].items() if k != "version"},
        "tool_groups": docs["tool_groups"]["tool_groups"],
        "surfaces": docs["surfaces"]["surfaces"],
        "teams": docs["teams"]["teams"],
        "user_groups": docs["user_groups"]["user_groups"],
        "grants": docs["grants"]["grants"],
        "rate_limits": docs["limits"]["rate_limits"],
        "providers": docs["providers"]["providers"],
        "identity": identity,
        "members": {email.lower(): _member(entry) for email, entry in users.items()},
        "blocked": (docs.get("env.blocked") or {}).get("blocked", []),
    }
    _cross_check(config, users, problems, warnings, env)
    return Compiled(config, problems, warnings)


def _member(entry: dict) -> dict:
    """`teams: [payments, platform:lead]` to {team: [roles]}; a team alone means its member role."""
    teams: dict[str, set[str]] = {}
    for item in entry.get("teams") or ():
        team, _, role = item.partition(":")
        teams.setdefault(team, set()).add(role or "member")
    return {
        "teams": {t: sorted(r) for t, r in sorted(teams.items())},
        "user_groups": sorted(entry.get("user_groups") or ()),
    }


def _cross_check(config: dict, users: dict, problems: list[str], warnings: list[str], env: str) -> None:
    tool_groups, surfaces, teams = config["tool_groups"], config["surfaces"], config["teams"]
    user_groups = config["user_groups"]

    def check_selector(where: str, to: dict) -> None:
        for entry in to.get("teams") or ():
            team, _, role = entry.partition(":")
            if team not in teams:
                problems.append(f"{where}: unknown team {team!r}")
            elif role and role not in teams[team]["roles"]:
                problems.append(f"{where}: team {team!r} has no role {role!r}")
        for ug in to.get("user_groups") or ():
            if ug not in user_groups:
                problems.append(f"{where}: unknown user group {ug!r}")

    seen_tools: dict[str, str] = {}
    for group_id, group in tool_groups.items():
        for tool in group["tools"]:
            if tool in seen_tools:
                problems.append(f"tool_groups.yaml: {tool!r} is in both {seen_tools[tool]!r} and {group_id!r}")
            seen_tools[tool] = group_id
    for surface_id, surface in surfaces.items():
        for group in surface["tool_groups"]:
            if group not in tool_groups:
                problems.append(f"surfaces.yaml: {surface_id}: unknown tool group {group!r}")
    granted: set[str] = set()
    grant_ids: set[str] = set()
    for grant in config["grants"]:
        if grant["id"] in grant_ids:
            problems.append(f"grants.yaml: duplicate grant id {grant['id']!r}")
        grant_ids.add(grant["id"])
        for group in grant["tool_groups"]:
            if group not in tool_groups:
                problems.append(f"grants.yaml: {grant['id']}: unknown tool group {group!r}")
            granted.add(group)
        check_selector(f"grants.yaml: {grant['id']}", grant["to"])
    for group in sorted(set(tool_groups) - granted):
        warnings.append(f"tool group {group!r} has no grant: available to no one")
    for override in config["rate_limits"]["tool_calls"].get("overrides") or ():
        check_selector(f"limits.yaml: {override['id']}", override["to"])

    identity, where = config["identity"], f"env/{env}/identity.yaml"
    for key in ("callers", "clients"):
        owners: dict[str, str] = {}
        for surface_id, ids in identity[key].items():
            if surface_id not in surfaces:
                problems.append(f"{where}: {key}: unknown surface {surface_id!r}")
            for i in ids:
                if i.lower() in owners:
                    problems.append(f"{where}: {key}: {i!r} is in {owners[i.lower()]!r} and {surface_id!r}")
                owners[i.lower()] = surface_id
    mode = identity["mode"]
    if not mode:
        warnings.append(f"env/{env}: no identity mode; every user will be refused")
    elif mode in LOCAL_ONLY_MODES and env != "local":
        problems.append(f"{where}: mode {mode!r} is allowed only in the local environment")
    elif mode in ("caller_token", "trusted_header") and not identity["callers"]:
        warnings.append(f"env/{env}: no callers declared; every user will be refused")
    elif mode == "oauth" and not identity["clients"]:
        warnings.append(f"env/{env}: no OAuth clients declared; every user will be refused")
    for email, entry in config["members"].items():
        roles = [f"{team}:{role}" for team, team_roles in entry["teams"].items() for role in team_roles]
        check_selector(f"env/{env}/users.yaml: {email}", {"teams": roles, "user_groups": entry["user_groups"]})
    if not users:
        warnings.append(f"env/{env}: no users.yaml: nobody is in any team")
