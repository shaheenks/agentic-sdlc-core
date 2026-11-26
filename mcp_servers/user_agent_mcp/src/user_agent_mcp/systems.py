"""Jira and repository tools, acting with the user's own connection on their team's systems only (FR-CONN-001,
FR-AUTHZ-003, FR-SDLC-002, FR-SDLC-003, FR-SDLC-005).

Argument constraints: which Jira projects and repositories a call may touch comes from the configuration
(`team_systems`), never from the arguments. Reads may touch the systems of any of the user's teams (in a team
run, that team's only); writes need a team run and touch that team's systems only, and each rests on an artifact
approved on the team's control repository and is recorded there (DEC-0012, `control.py`). A team lists its Jira
projects, Confluence spaces and repositories, each with one default, used when a call names none.
"""

import asyncio
import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from sdlc_connectors import ConnectorError, Credential, Jira, repository

from user_agent_mcp.errors import ToolError

if TYPE_CHECKING:
    from user_agent_mcp.platform import Caller, Platform

ISSUE_KEY = re.compile(r"^([A-Z][A-Z0-9_]{0,19})-[1-9][0-9]{0,9}$")
CONSTRAINT = "constraint_denied"


def scope(caller: "Caller") -> dict[str, dict[str, Any]]:
    """The systems this call may read: the run's team's, or in the user's own runs, those of all their teams."""
    systems = caller.bundle.config.get("team_systems") or {}
    teams = [caller.policy.team] if caller.policy.team else sorted(caller.memberships.teams)
    return {t: systems[t] for t in teams if t in systems}


def _run_team(caller: "Caller") -> str:
    if not caller.policy.team:
        raise ToolError(
            "team_run_required", "changes to Jira or a repository are made only in a run for one of your teams"
        )
    return caller.policy.team


def _credential(platform: "Platform", caller: "Caller", provider: str) -> Credential:
    try:
        token, account = platform.connections.credential(caller.identity.user_id, provider)
    except ToolError as exc:
        if exc.code == "not_found":
            raise ToolError("not_connected", f"connect your {provider} account first (connection_start)") from exc
        raise
    return Credential(token, account)


async def _call[T](fn: Callable[[], T]) -> T:
    try:
        return await asyncio.to_thread(fn)
    except ConnectorError as exc:
        raise ToolError(f"downstream_{exc.code}", exc.message) from exc


def _edition(caller: "Caller", provider: str) -> tuple[str, str]:
    config = (caller.bundle.config.get("providers") or {}).get(provider) or {}
    return config.get("system", ""), config.get("edition", "")


OPEN = "statusCategory != Done"  # open issues: not in a done status

# Jira -----------------------------------------------------------------------------------------------------


def _teams(caller: "Caller", write: bool) -> dict[str, dict[str, Any]]:
    return {(t := _run_team(caller)): (scope(caller).get(t) or {})} if write else scope(caller)


def _default_team(caller: "Caller", teams: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """The team whose defaults apply: the run's team, or the user's only team with systems."""
    if caller.policy.team:
        return teams.get(caller.policy.team)
    return next(iter(teams.values())) if len(teams) == 1 else None


def _jira_projects(caller: "Caller", write: bool) -> dict[str, tuple[str, dict[str, Any]]]:
    """Project key -> (team, Jira settings) that this call may touch."""
    return {j["project"]: (team, j) for team, s in _teams(caller, write).items() for j in s.get("jira") or ()}


def _jira(platform: "Platform", caller: "Caller", settings: dict[str, Any]) -> Jira:
    _, edition = _edition(caller, settings["provider"])
    return Jira(settings["base_url"], edition, _credential(platform, caller, settings["provider"]))


def _project_of(key: str, allowed: dict[str, Any]) -> str:
    match = ISSUE_KEY.match(key or "")
    if not match:
        raise ToolError("invalid_argument", "key must be a Jira issue key such as PAY-12")
    if match.group(1) not in allowed:
        raise ToolError(CONSTRAINT, f"{match.group(1)} is not a Jira project of your team")
    return match.group(1)


def _pick(item: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {k: item[k] for k in keys if k in item}


async def team_systems(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    jira_keys = ("project", "base_url", "default", "epic_type", "feature_type", "story_type")
    return {
        "team": caller.policy.team,
        "teams": {
            team: {
                "jira": [_pick(j, jira_keys) for j in s.get("jira") or ()],
                "confluence": [
                    _pick(c, ("space", "base_url", "parent_page", "default")) for c in s.get("confluence") or ()
                ],
                "repositories": [
                    _pick(r, ("repo", "provider", "default_branch", "design_path", "default"))
                    for r in s.get("repositories") or ()
                ],
                "control_repo": _pick(s["control_repo"], ("repo", "provider", "branch"))
                if s.get("control_repo")
                else None,
            }
            for team, s in scope(caller).items()
        },
    }


async def jira_get_issue(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    allowed = _jira_projects(caller, write=False)
    key = args.get("key") or ""
    project = _project_of(key, allowed)
    _, settings = allowed[project]
    jira = _jira(platform, caller, settings)
    issue = await _call(lambda: jira.get_issue(key))
    found = issue.describe()
    if issue.issue_type == settings["feature_type"]:
        stories = await _call(lambda: jira.children(key, project))
        found["stories"] = [s.describe() for s in stories]
    return found


def _jql_text(text: str) -> str:
    cleaned = re.sub(r'["\\]', " ", text).strip()[:200]
    return f'text ~ "{cleaned}"' if cleaned else ""


async def jira_search(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    """Issues of the team's projects matching words, an issue type or a status. The query is built here; the
    model never writes JQL, so it cannot reach another project."""
    allowed = _jira_projects(caller, write=False)
    if not allowed:
        return {"issues": []}
    sites: dict[tuple[str, str], list[dict[str, Any]]] = {}  # one query per site, default projects first
    for _, settings in sorted(allowed.values(), key=lambda v: (not v[1]["default"], v[1]["project"])):
        sites.setdefault((settings["provider"], settings["base_url"]), []).append(settings)
    results = []
    for projects in sites.values():
        settings = projects[0]
        keys = ", ".join(f'"{p["project"]}"' for p in projects)
        clauses = [f'project = "{settings["project"]}"' if len(projects) == 1 else f"project in ({keys})"]
        if args.get("text"):
            clauses.append(_jql_text(str(args["text"])))
        if args.get("open_only"):
            clauses.append(OPEN)
        for arg, field in (("issue_type", "issuetype"), ("status", "status")):
            value = args.get(arg)
            if value:
                if not isinstance(value, str) or not re.match(r"^[A-Za-z0-9 _-]{1,60}$", value):
                    raise ToolError("invalid_argument", f"{arg} must be a plain name")
                clauses.append(f'{field} = "{value}"')
        jql = " AND ".join(c for c in clauses if c) + " ORDER BY updated DESC"
        jira = _jira(platform, caller, settings)
        found = await _call(lambda jira=jira, jql=jql: jira.search(jql, limit=20))
        results.extend(i.describe() | {"description": i.description[:500]} for i in found)
    return {"issues": results[:20]}


SIZES = ("XS", "S", "M", "L", "XL")
POINTS = (1, 2, 3, 5, 8, 13)
POINTS_FIELDS = ("Story point estimate", "Story Points", "Story points")


def _estimates(feature: dict[str, Any], stories: list[dict[str, Any]]) -> None:
    size = feature.get("estimate")
    if size is not None and size not in SIZES:
        raise ToolError("invalid_argument", f"a feature's estimate is one of {', '.join(SIZES)}")
    for story in stories:
        points = story.get("story_points")
        if points is not None and points not in POINTS:
            raise ToolError("invalid_argument", f"story points are one of {', '.join(map(str, POINTS))}")


def _with_estimate(description: str, line: str) -> str:
    return f"{line}\n\n{description}".strip() if line else description


async def jira_create_feature(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    """The approved feature in Jira as the user (DEC-0013): under its epic (an existing one, or one created now when
    the user confirmed it), the feature as an issue of the team's feature type, and each user story as a sub-task of
    it. Open issues with the same summary are reused, never created twice; the keys are recorded on the feature's
    branch of the team's control repository."""
    from user_agent_mcp.control import Control, _check_id, path_of

    allowed = _jira_projects(caller, write=True)
    if not allowed:
        raise ToolError(CONSTRAINT, "your team has no Jira project in this environment")
    project = args.get("project") or next(p for p, (_, s) in allowed.items() if s["default"])
    if project not in allowed:
        raise ToolError(CONSTRAINT, f"{project} is not a Jira project of your team")
    _, settings = allowed[project]
    control_id = _check_id(args.get("control_id"))
    feature, stories, epic = args.get("feature") or {}, args.get("stories") or [], args.get("epic") or {}
    if not isinstance(feature, dict) or not isinstance(stories, list) or not 1 <= len(stories) <= 30:
        raise ToolError("invalid_argument", "give a feature and 1 to 30 stories")
    for item in [feature, *stories]:
        if not isinstance(item, dict) or not isinstance(item.get("summary"), str) or not item["summary"].strip():
            raise ToolError("invalid_argument", "every item needs a summary")
    if not isinstance(epic, dict) or not (epic.get("key") or (epic.get("create") and epic.get("summary"))):
        raise ToolError("invalid_argument", "every feature sits under an epic: give its key, or a summary with create")
    _estimates(feature, stories)
    control = Control(platform, caller)
    approved = await _call(lambda: control.require_approved(control_id, "feature"))
    done = [
        w
        for w in (await _call(lambda: control.links(control_id))).get("writes") or ()
        if w.get("action") == "create_feature" and not w.get("error")
    ]
    if done:
        raise ToolError("already_done", f"{control_id} is already in Jira as {done[-1]['results'].get('feature')}")
    jira = _jira(platform, caller, settings)

    def open_issue(issue_type: str, summary: str, parent: str | None = None):
        """An open issue of this type and summary (under `parent`, when given): reused instead of a new one."""
        if parent:
            candidates = jira.children(parent, project)
        else:
            jql = f'project = "{project}" AND issuetype = "{issue_type}" AND {OPEN} AND {_jql_text(summary)}'
            candidates = jira.search(jql, limit=20)
        wanted = summary.strip().lower()
        return next((i for i in candidates if i.summary.strip().lower() == wanted and i.issue_type == issue_type), None)

    results: dict[str, Any] = {"project": project, "site": settings["base_url"], "stories": [], "reused": []}
    entry = {
        "action": "create_feature",
        "system": "jira",
        "artifact": path_of(control_id, "feature"),
        "artifact_commit": approved.get("commit"),
        "approved_by": approved.get("approved_by") or approved.get("merged_by"),
        "results": results,
    }
    size = feature.get("estimate")
    size_line = f"High-level estimate: {size}" + (
        f" ({feature['estimate_note']})"
        if isinstance(feature.get("estimate_note"), str) and feature["estimate_note"]
        else ""
    )
    points_field = settings.get("story_points_field")
    if not points_field and any(s.get("story_points") for s in stories):
        points_field = await _call(lambda: jira.field_id(POINTS_FIELDS))
    try:
        # the epic
        if epic.get("key"):
            epic_key = str(epic["key"])
            _project_of(epic_key, {project: True})
            found_epic = await _call(lambda: jira.get_issue(epic_key))
            if found_epic.issue_type != settings["epic_type"]:
                raise ToolError("invalid_argument", f"{epic_key} is a {found_epic.issue_type}, not an epic")
        else:
            existing = await _call(lambda: open_issue(settings["epic_type"], str(epic["summary"])))
            if existing:
                epic_key = existing.key
                results["reused"].append(epic_key)
            else:
                made_epic = await _call(
                    lambda: jira.create_issue(
                        project, settings["epic_type"], str(epic["summary"]), str(epic.get("description") or "")
                    )
                )
                epic_key, results["epic_created"] = made_epic.key, True
        results["epic"] = epic_key
        # the feature, under the epic
        created = await _call(lambda: open_issue(settings["feature_type"], feature["summary"]))
        if created:
            results["reused"].append(created.key)
        else:
            created = await _call(
                lambda: jira.create_issue(
                    project,
                    settings["feature_type"],
                    feature["summary"],
                    _with_estimate(str(feature.get("description") or ""), size_line if size else ""),
                    parent=epic_key,
                    labels=[f"size-{size}"] if size else None,
                )
            )
            link = f"{control.settings['repo']}/{path_of(control_id, 'feature')} on {control.home(control_id)}"
            await _call(
                lambda: jira.add_web_link(
                    created.key,
                    approved.get("url") or _repo_url(control, control_id) or link,
                    f"sdlc-control {control_id}",
                )
            )
        results["feature"] = created.key
        if size:
            results["estimate"] = size
        # the user stories, as sub-tasks of the feature
        for story in stories:
            points = story.get("story_points")
            existing_story = await _call(lambda s=story: open_issue(settings["story_type"], s["summary"], created.key))
            if existing_story:
                results["stories"].append(existing_story.key)
                results["reused"].append(existing_story.key)
                continue
            description = _with_estimate(
                str(story.get("description") or ""), f"Story points: {points}" if points else ""
            )

            def make(s=story, d=description, p=points, field=points_field):
                extra = {field: p} if field and p else None
                kind, parent = settings["story_type"], created.key
                try:
                    return jira.create_issue(project, kind, s["summary"], d, parent=parent, extra=extra)
                except ConnectorError as exc:
                    if extra and exc.code == "invalid" and field in exc.message:  # the field is not on this screen
                        return jira.create_issue(project, kind, s["summary"], d, parent=parent)
                    raise

            made = await _call(make)
            results["stories"].append(made.key)
            if points:
                results.setdefault("story_points", {})[made.key] = points
    except ToolError as exc:
        entry["error"] = exc.code
        await _call(lambda: control.record(control_id, entry))
        raise
    await _call(lambda: control.record(control_id, entry))
    return {
        "control_id": control_id,
        "epic": {"key": results["epic"], "created": bool(results.get("epic_created"))},
        "feature": {"key": created.key, "url": created.url},
        "stories": results["stories"],
        "reused": results["reused"],
        "project": project,
        "recorded": f"features/{control_id}/links.yaml on {control.home(control_id)}",
    }


def _repo_url(control: Any, control_id: str) -> str | None:
    """A browser link to the feature's folder on its branch, for GitHub; None elsewhere."""
    api = str(control.client.http.base_url) if hasattr(control.client, "http") else ""
    if "api.github.com" not in api:
        return None
    return f"https://github.com/{control.settings['repo']}/tree/{control.home(control_id)}/features/{control_id}"


async def jira_link_design(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    """Links the approved design specification to its Jira feature, and records the link (DEC-0012)."""
    from user_agent_mcp.control import CONTROL_ID, Control, path_of

    control_id = args.get("control_id")
    if not isinstance(control_id, str) or not CONTROL_ID.match(control_id):
        raise ToolError("invalid_argument", "control_id of the published design (such as F-20261125-refunds)")
    control = Control(platform, caller)
    approved = await _call(lambda: control.require_approved(control_id, "design"))
    writes = (await _call(lambda: control.links(control_id))).get("writes") or []
    key = next((w["results"].get("feature") for w in writes if w.get("action") == "create_feature"), None)
    if not key:
        raise ToolError("not_found", f"{control_id} has no Jira feature recorded")
    allowed = _jira_projects(caller, write=True)
    project = _project_of(key, allowed)
    jira = _jira(platform, caller, allowed[project][1])
    url = approved.get("url") or path_of(control_id, "design")
    await _call(lambda: jira.add_web_link(key, url, f"Design specification ({control_id})"))
    entry = {
        "action": "link_design",
        "system": "jira",
        "artifact": path_of(control_id, "design"),
        "artifact_commit": approved["commit"],
        "approved_by": approved.get("merged_by"),
        "results": {"feature": key, "url": url},
    }
    await _call(lambda: control.record(control_id, entry))
    return {"control_id": control_id, "feature": key, "linked": url}


# Repositories ---------------------------------------------------------------------------------------------


def _repo(platform: "Platform", caller: "Caller", name: Any, write: bool):
    teams = _teams(caller, write)
    if not name:  # the team's default repository
        default = _default_team(caller, teams) or {}
        name = next((r["repo"] for r in default.get("repositories") or () if r["default"]), None)
        if not name:
            raise ToolError("invalid_argument", "name the repository (owner/name); see team_systems")
    for systems in teams.values():
        for repo in systems.get("repositories") or ():
            if isinstance(name, str) and repo["repo"].lower() == name.lower():
                system, edition = _edition(caller, repo["provider"])
                base_url = repo.get("base_url") or (caller.bundle.config["providers"][repo["provider"]].get("base_url"))
                client = repository(
                    system, edition, base_url, repo["repo"], _credential(platform, caller, repo["provider"])
                )
                return client, repo
    raise ToolError(CONSTRAINT, "that repository is not one of your team's")


async def repo_list(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    client, repo = _repo(platform, caller, args.get("repo"), write=False)
    path = str(args.get("path") or "").strip("/")
    entries = await _call(lambda: client.list_dir(path, args.get("ref")))
    return {"repo": repo["repo"], "path": path, "entries": entries[:200]}


async def repo_pull_requests(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    """The open pull requests of one of the team's repositories (its default when none is named): to check for a
    similar one before raising another."""
    client, repo = _repo(platform, caller, args.get("repo"), write=False)
    found = await _call(client.open_pull_requests)
    return {
        "repo": repo["repo"],
        "pull_requests": [
            {"number": p.number, "title": p.title, "url": p.url, "branch": p.branch, "author": p.author} for p in found
        ],
    }


async def repo_read_file(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    client, repo = _repo(platform, caller, args.get("repo"), write=False)
    path = str(args.get("path") or "")
    content = await _call(lambda: client.read_file(path, args.get("ref")))
    return {"repo": repo["repo"], "path": path, "content": content[:100_000], "truncated": len(content) > 100_000}


# The connection test (FR-CONN-001) ------------------------------------------------------------------------


REFUSED = ("unauthorized", "forbidden", "invalid")


async def sign_in(caller: "Caller", provider: str, credential: Credential, base_url: str | None) -> dict[str, Any]:
    """Signs in to the provider with a credential and says as whom: `ok` with the account, `refused` when the
    provider rejects it, or `untested` when there is nothing to test against or the server cannot be reached."""
    system, edition = _edition(caller, provider)
    if system == "confluence":
        return {"status": "untested", "reason": "Confluence sign-in is checked once the Confluence tools exist"}
    if system == "jira" and not base_url:  # Jira Cloud: the site of one of the user's teams
        sites = [
            j["base_url"] for s in scope(caller).values() for j in s.get("jira") or () if j["provider"] == provider
        ]
        base_url = sites[0] if sites else None
    if not base_url:
        return {
            "status": "untested",
            "reason": "none of your teams uses this provider here, so there is no site to test",
        }
    try:
        client: Any = (
            Jira(base_url, edition, credential)
            if system == "jira"
            else repository(system, edition, base_url, "x/x", credential)
        )
        who = await asyncio.to_thread(client.whoami)
    except ConnectorError as exc:
        if exc.code in REFUSED or exc.code == "account_required":
            return {"status": "refused", "reason": exc.code}
        return {"status": "untested", "reason": f"the server could not be checked ({exc.code})"}
    return {"status": "ok", "account": who.get("account")}


async def connection_test(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    """Signs in to the provider with the user's stored connection and says as whom; the token is never returned."""
    provider = args.get("provider")
    system, _ = _edition(caller, provider) if isinstance(provider, str) else ("", "")
    if not system:
        raise ToolError("unknown_provider", "unknown provider")
    credential = _credential(platform, caller, provider)
    stored = platform.connections.metadata(caller.identity.user_id, provider)
    return {"provider": provider, **(await sign_in(caller, provider, credential, stored.get("base_url")))}
