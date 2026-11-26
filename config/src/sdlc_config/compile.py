"""YAML files to one compiled, cross-checked configuration."""

import json
import pathlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

SHARED_KINDS = (
    "platform",
    "tool_groups",
    "surfaces",
    "limits",
    "providers",
)
# Environment configuration, env/<env>/<kind>.yaml: identity, users and the block list; the teams and user groups
# with what they are given and, for teams, their systems; and the knowledge sources.
ENV_KINDS = ("identity", "users", "blocked", "teams", "user_groups", "sources")
ENV_ONLY = ("teams", "user_groups", "sources")  # once shared files; refused there now
# Kinds whose items may also be one file each, env/<env>/<kind>/<id>.yaml, next to or instead of <kind>.yaml.
ITEM_FOLDERS = ("teams", "sources")
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


def _read(path: Path, problems: list[str]) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        problems.append(f"{path.name}: invalid YAML: {exc}")
        return None


def _validate(doc: Any, kind: str, where: str, schemas: Path, problems: list[str]) -> dict | None:
    schema = json.loads((schemas / f"{kind}.schema.json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(doc), key=lambda e: list(e.absolute_path))
    for error in errors:
        at = "/".join(str(p) for p in error.absolute_path) or "(top)"
        problems.append(f"{where}: {at}: {error.message}")
    return None if errors else doc


def _load(path: Path, kind: str, schemas: Path, problems: list[str]) -> dict | None:
    before = len(problems)
    doc = _read(path, problems)
    if len(problems) > before:
        return None
    return _validate(doc, kind, path.as_posix(), schemas, problems)


def _load_items(config_dir: Path, env: str, kind: str, schemas: Path, docs: dict, problems: list[str]) -> None:
    """Adds env/<env>/<kind>/<id>.yaml, one item per file named by its ID, to the items of env/<env>/<kind>.yaml."""
    folder = config_dir / "env" / env / kind
    if not folder.is_dir():
        return
    items = dict((docs.get(f"env.{kind}") or {}).get(kind) or {})
    origin = dict.fromkeys(items, f"env/{env}/{kind}.yaml")
    for path in sorted(folder.iterdir()):
        if path.suffix not in (".yaml", ".yml") or not path.is_file():
            continue
        where, name = f"env/{env}/{kind}/{path.name}", path.stem
        before = len(problems)
        body = _read(path, problems)
        if len(problems) > before or _validate({kind: {name: body}}, kind, where, schemas, problems) is None:
            continue
        if name in origin:
            problems.append(f"{where}: {name!r} is also defined in {origin[name]}")
            continue
        items[name], origin[name] = body, where
    docs[f"env.{kind}"] = {kind: items}


def compile_config(config_dir: Path, env: str) -> Compiled:
    problems: list[str] = []
    warnings: list[str] = []
    schemas = config_dir / "schemas"
    docs: dict[str, dict] = {}
    env_dir = config_dir / "env" / env
    if not env_dir.is_dir():
        warnings.append(f"env/{env}/: missing; services will refuse every user in this environment")
    for kind in SHARED_KINDS:
        path = config_dir / f"{kind}.yaml"
        if not path.is_file():
            problems.append(f"{kind}.yaml: missing")
            continue
        doc = _load(path, kind, schemas, problems)
        if doc is not None:
            docs[kind] = doc
    if (env_dir / "systems.yaml").is_file():
        problems.append(f"env/{env}/systems.yaml: team systems moved to `systems` in env/{env}/teams.yaml")
    for kind in ENV_KINDS:
        path = env_dir / f"{kind}.yaml"
        if path.is_file():
            doc = _load(path, kind, schemas, problems)
            if doc is not None:
                docs[f"env.{kind}"] = doc
    for kind in ITEM_FOLDERS:
        _load_items(config_dir, env, kind, schemas, docs, problems)
    for kind in ENV_ONLY:
        if (config_dir / f"{kind}.yaml").is_file():
            problems.append(f"{kind}.yaml: {kind} are environment configuration now: move it to env/{env}/{kind}.yaml")
        if env_dir.is_dir() and f"env.{kind}" not in docs:
            warnings.append(f"env/{env}: no {kind}.yaml: no {kind.replace('_', ' ')} in this environment")
        docs[kind] = docs.get(f"env.{kind}") or {kind: {}}
    if problems:
        return Compiled({}, problems, warnings)

    identity = {**UNCONFIGURED, **(docs.get("env.identity") or {})}
    users = (docs.get("env.users") or {}).get("users") or {}
    config: dict[str, Any] = {
        "platform": {k: v for k, v in docs["platform"].items() if k != "version"},
        "tool_groups": docs["tool_groups"]["tool_groups"],
        "surfaces": docs["surfaces"]["surfaces"],
        "teams": {t: {k: v for k, v in e.items() if k != "systems"} for t, e in docs["teams"]["teams"].items()},
        "user_groups": docs["user_groups"]["user_groups"],
        "grants": _grants(docs),
        "rate_limits": docs["limits"]["rate_limits"],
        "providers": docs["providers"]["providers"],
        "sources": docs["sources"]["sources"],
        "identity": identity,
        "members": _with_team_groups(
            {email.lower(): _member(entry) for email, entry in users.items()}, docs["user_groups"]["user_groups"]
        ),
        "blocked": (docs.get("env.blocked") or {}).get("blocked", []),
        "team_systems": _team_systems({t: e["systems"] for t, e in docs["teams"]["teams"].items() if e.get("systems")}),
    }
    _cross_check(config, users, problems, warnings, env)
    return Compiled(config, problems, warnings)


JIRA_DEFAULTS = {  # Epic -> Feature (a story-level issue) -> User Stories as its sub-tasks (DEC-0013)
    "epic_type": "Epic",
    "feature_type": "Story",
    "story_type": "Sub-task",
    "story_link": "parent",
}


GRANTED = ("tool_groups", "sources")


def _grants(docs: dict) -> list[dict]:
    """Grants from where they are declared: `everyone: true` on tool groups and sources, and the tool groups and
    sources of each team, team role and user group. The Access Policy reads only this compiled list."""

    def grant(grant_id: str, given: dict, to: dict) -> list[dict]:
        kept = {k: sorted(given[k]) for k in GRANTED if given.get(k)}
        return [{"id": grant_id, **kept, "to": to}] if kept else []

    everyone = {kind: [name for name, entry in docs[kind][kind].items() if entry.get("everyone")] for kind in GRANTED}
    out = grant("everyone", everyone, {"everyone": True})  # teams and user groups: from the environment
    for team, entry in docs["teams"]["teams"].items():
        out += grant(f"team:{team}", entry, {"teams": [team]})
        for role, given in (entry.get("role_grants") or {}).items():
            out += grant(f"team:{team}:{role}", given, {"teams": [f"{team}:{role}"]})
    for group, entry in docs["user_groups"]["user_groups"].items():
        out += grant(f"user_group:{group}", entry, {"user_groups": [group]})
    return out


def _where(grant_id: str, env: str) -> str:
    kind, _, name = grant_id.partition(":")
    return {
        "everyone": "everyone: true",
        "team": f"env/{env}/teams (teams.yaml or teams/{name.partition(':')[0]}.yaml): {name}",
        "user_group": f"env/{env}/user_groups.yaml: {name}",
    }[kind]


def _with_default(items: list[dict]) -> list[dict]:
    """A single entry is the default; otherwise `default` is what the entry says."""
    return [{**item, "default": bool(item.get("default")) or len(items) == 1} for item in items]


def _team_systems(teams: dict) -> dict:
    """Each team's Jira projects, Confluence spaces and repositories, with defaults filled in."""
    out = {}
    for team, systems in teams.items():
        entry: dict = {
            "jira": _with_default(
                [{**JIRA_DEFAULTS, **j, "base_url": j["base_url"].rstrip("/")} for j in systems.get("jira") or ()]
            ),
            "confluence": _with_default(
                [{**c, "base_url": c["base_url"].rstrip("/")} for c in systems.get("confluence") or ()]
            ),
            "repositories": _with_default([{"default_branch": "main", **r} for r in systems.get("repositories") or ()]),
        }
        if systems.get("control_repo"):
            entry["control_repo"] = {"branch": "main", **systems["control_repo"]}
        out[team] = entry
    return out


def _with_team_groups(members: dict, user_groups: dict) -> dict:
    """Adds each user group that lists one of the member's teams (`payments`) or team roles (`payments:lead`)."""
    for entry in members.values():
        held = {t for t in entry["teams"]} | {f"{t}:{r}" for t, roles in entry["teams"].items() for r in roles}
        joined = {group for group, g in user_groups.items() if held & set(g.get("teams") or ())}
        entry["user_groups"] = sorted(set(entry["user_groups"]) | joined)
    return members


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
    readable: set[str] = set()
    for grant in config["grants"]:
        where = _where(grant["id"], env)
        for group in grant.get("tool_groups") or ():
            if group not in tool_groups:
                problems.append(f"{where}: unknown tool group {group!r}")
            granted.add(group)
        for source in grant.get("sources") or ():
            if source not in config["sources"]:
                problems.append(f"{where}: unknown source {source!r}")
            readable.add(source)
        check_selector(where, grant["to"])
    for group in sorted(set(tool_groups) - granted):
        warnings.append(f"tool group {group!r} is given to no team, user group or everyone: available to no one")
    for source in sorted(set(config["sources"]) - readable):
        warnings.append(f"source {source!r} is given to no team, user group or everyone: readable by no one")
    for source_id, source in config["sources"].items():
        if source["kind"] == "git" and not source["location"].startswith("https://"):
            problems.append(f"env/{env}/sources.yaml: {source_id}: a git location must be an https URL")
        if source["kind"] != "git" and ("ref" in source or "credential" in source):
            problems.append(f"env/{env}/sources.yaml: {source_id}: ref and credential are for git sources only")
        signin = [k for k in ("credential_scheme", "credential_username") if k in source]
        if signin and "credential" not in source:
            problems.append(f"env/{env}/sources.yaml: {source_id}: {' and '.join(signin)} without a credential")
        if source.get("credential_scheme") == "bearer" and "credential_username" in source:
            problems.append(f"env/{env}/sources.yaml: {source_id}: a bearer credential has no username")
        location = source["location"]
        if (
            source["kind"] == "folder"
            and not location.startswith("gs://")
            and (".." in pathlib.PurePosixPath(location).parts or location.startswith(("/", "\\")) or ":" in location)
        ):
            problems.append(f"env/{env}/sources.yaml: {source_id}: a folder location cannot leave the ingest root")
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
    providers = config["providers"]
    control_owners: dict[str, str] = {}
    for team, systems in config["team_systems"].items():
        where = f"env/{env}/teams.yaml: {team}: systems"
        for kind, name_key in (("jira", "project"), ("confluence", "space"), ("repositories", "repo")):
            items = systems[kind]
            defaults = [i[name_key] for i in items if i["default"]]
            if len(defaults) > 1:
                problems.append(f"{where}: {kind}: more than one default ({', '.join(defaults)})")
            elif items and not defaults:
                problems.append(f"{where}: {kind}: mark one entry `default: true`")
        seen_projects: set[str] = set()
        for jira in systems["jira"]:
            if (providers.get(jira["provider"]) or {}).get("system") != "jira":
                problems.append(f"{where}: {jira['provider']!r} is not a Jira provider")
            if jira["project"] in seen_projects:
                problems.append(f"{where}: Jira project {jira['project']!r} is listed twice")
            seen_projects.add(jira["project"])
        seen_spaces: set[tuple[str, str]] = set()
        for space in systems["confluence"]:
            if (providers.get(space["provider"]) or {}).get("system") != "confluence":
                problems.append(f"{where}: {space['provider']!r} is not a Confluence provider")
            key = (space["base_url"].lower(), space["space"], space.get("parent_page", ""))
            if key in seen_spaces:
                problems.append(f"{where}: Confluence space {space['space']!r} is listed twice")
            seen_spaces.add(key)
        seen_repos: set[str] = set()
        for repo in systems["repositories"]:
            system = (providers.get(repo["provider"]) or {}).get("system")
            if system not in ("github", "bitbucket"):
                problems.append(f"{where}: {repo['provider']!r} is not a repository provider")
            elif (providers[repo["provider"]].get("edition") == "data_center") and not repo.get("base_url"):
                problems.append(f"{where}: {repo['repo']}: a Data Center repository needs base_url")
            if repo["repo"].lower() in seen_repos:
                problems.append(f"{where}: {repo['repo']!r} is listed twice")
            seen_repos.add(repo["repo"].lower())
        control = systems.get("control_repo")
        if control:
            name = control["repo"]
            system = (providers.get(control["provider"]) or {}).get("system")
            if system not in ("github", "bitbucket"):
                problems.append(f"{where}: control_repo: {control['provider']!r} is not a repository provider")
            elif providers[control["provider"]].get("edition") == "data_center" and not control.get("base_url"):
                problems.append(f"{where}: control_repo: a Data Center repository needs base_url")
            if name.lower() in seen_repos:
                problems.append(f"{where}: control_repo: {name!r} is also a product repository")
            if name.lower() in control_owners:
                problems.append(f"{where}: control_repo: {name!r} is also team {control_owners[name.lower()]!r}'s")
            control_owners[name.lower()] = team
    for group, entry in user_groups.items():
        check_selector(f"env/{env}/user_groups.yaml: {group}: teams", {"teams": entry.get("teams") or []})
    for email, entry in config["members"].items():
        roles = [f"{team}:{role}" for team, team_roles in entry["teams"].items() for role in team_roles]
        check_selector(f"env/{env}/users.yaml: {email}", {"teams": roles, "user_groups": entry["user_groups"]})
    if not users:
        warnings.append(f"env/{env}: no users.yaml: nobody is in any team")
