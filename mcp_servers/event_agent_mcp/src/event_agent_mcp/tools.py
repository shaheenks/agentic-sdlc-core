"""The tools of unattended runs (DEC-0015, FR-SDLC-006, FR-TRIG-003, FR-AGT-004).

They act on the run's team's control repository and product repositories with the machine user's system connection.
Approvals are checked here, never by the agent: a plan only for an approved design, an implementation only for an
approved plan, each on the feature's branch. Pull requests go only from `sdlc/` branches into `feature/` branches;
nothing here merges, approves or pushes to another branch. Every write is recorded on the feature branch.
"""

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sdlc_connectors import ConnectorError, Credential, clone_url, repository
from sdlc_control import (
    CONTROL_ID,
    MAX_ARTIFACT,
    MAX_CHANGES,
    MAX_FILE,
    ControlError,
    ControlRepository,
    check_changes,
    feature_branch,
    front_matter,
    implementation_branch,
    open_implementation,
    open_plan,
    plan_kind,
    require_approved,
    without_front_matter,
)
from sdlc_control import jira_keys as _jira_keys
from sdlc_control import targets as _targets

from event_agent_mcp.errors import ToolError

if TYPE_CHECKING:
    from event_agent_mcp.platform import Platform, Run

Handler = Callable[["Platform", "Run", dict[str, Any]], Awaitable[dict[str, Any]]]
FILE = re.compile(r"^[A-Za-z0-9_.-]{1,100}\.(md|yaml)$")
MAX_LOG = 4_000


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Handler
    write: bool = False


def _schema(properties: dict[str, Any], required: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


async def _call[T](fn: Callable[[], T]) -> T:
    try:
        return await asyncio.to_thread(fn)
    except ConnectorError as exc:
        raise ToolError(f"downstream_{exc.code}", exc.message) from exc
    except ControlError as exc:
        raise ToolError(exc.code, exc.message) from exc


def _check_id(value: Any) -> str:
    if not isinstance(value, str) or not CONTROL_ID.match(value):
        raise ToolError("invalid_argument", "control_id looks like F-20261126-refunds")
    return value


# The run's team's systems, with the system connection ----------------------------------------------------------


def _systems(run: "Run") -> dict[str, Any]:
    return (run.bundle.config.get("team_systems") or {}).get(run.team) or {}


def _client(platform: "Platform", run: "Run", entry: dict[str, Any]):
    provider = entry["provider"]
    config = (run.bundle.config.get("providers") or {}).get(provider) or {}
    token = platform.settings.system_token(provider)
    if not token:
        raise ToolError("not_connected", f"no system connection for {provider} in this environment")
    account = ((run.bundle.config.get("system") or {}).get("machine_users") or {}).get(provider)
    base_url = entry.get("base_url") or config.get("base_url") or ""
    client = repository(
        config.get("system", ""), config.get("edition", ""), base_url, entry["repo"], Credential(token, account)
    )
    return client, config, base_url


def _control(platform: "Platform", run: "Run") -> ControlRepository:
    settings = _systems(run).get("control_repo")
    if not settings:
        raise ToolError("constraint_denied", "the team has no control repository in this environment")
    client, _, _ = _client(platform, run, settings)
    machine = ((run.bundle.config.get("system") or {}).get("machine_users") or {}).get(settings["provider"])
    control = ControlRepository(
        client, settings.get("branch", "main"), settings.get("system_accounts") or (), f"system:{machine or 'unknown'}"
    )
    control.settings = settings  # type: ignore[attr-defined]
    return control


def _target(platform: "Platform", run: "Run", name: Any):
    """One of the team's product repositories, by owner/name or by name alone."""
    if not isinstance(name, str) or not name:
        raise ToolError("invalid_argument", "name the repository (owner/name)")
    for entry in _systems(run).get("repositories") or ():
        if name.lower() in (entry["repo"].lower(), entry["repo"].rsplit("/", 1)[-1].lower()):
            client, config, base_url = _client(platform, run, entry)
            return client, entry, config, base_url
    raise ToolError("constraint_denied", f"{name} is not one of the team's repositories")


# Reading --------------------------------------------------------------------------------------------------------


async def feature_status(platform: "Platform", run: "Run", args: dict[str, Any]) -> dict[str, Any]:
    """The feature's artifacts and their approvals on its branch, the plan of each target repository, its Jira keys
    and what has been written from it."""
    control_id = _check_id(args.get("control_id"))
    control = _control(platform, run)

    def gather() -> dict[str, Any]:
        links = control.links(control_id)
        targets = _targets(links) or [r["repo"] for r in _systems(run).get("repositories") or () if r.get("default")]
        artifacts = {kind: control.approval(control_id, kind) for kind in ("feature", "design")}
        plans = {repo: control.approval(control_id, plan_kind(repo)) for repo in targets}
        if args.get("include_content"):
            for found in [*artifacts.values(), *plans.values()]:
                if found["published"]:
                    found["content"] = without_front_matter(control.read(found["path"], found["branch"]) or "")
        return {
            "control_id": control_id,
            "team": run.team,
            "control_repo": control.settings["repo"],  # type: ignore[attr-defined]
            "branch": control.home(control_id),
            "artifacts": artifacts,
            "plans": plans,
            "target_repositories": targets,
            "jira_keys": _jira_keys(links),
            "writes": links.get("writes") or [],
            "open_pull_requests": [p for p in control.open_pull_requests() if p.get("control_id") == control_id],
        }

    return await _call(gather)


async def control_read_file(platform: "Platform", run: "Run", args: dict[str, Any]) -> dict[str, Any]:
    """One file of the feature's folder on its branch, such as design.md or plan-app.md, with its front matter apart."""
    control_id = _check_id(args.get("control_id"))
    name = args.get("file")
    if not isinstance(name, str) or not FILE.match(name):
        raise ToolError("invalid_argument", "file is a name in the feature's folder, such as design.md")
    control = _control(platform, run)
    path = f"features/{control_id}/{name}"
    text = await _call(lambda: control.read(path, control.home(control_id)))
    if text is None:
        raise ToolError("not_found", f"{path} is not on the feature's branch")
    return {"path": path, "meta": front_matter(text), "content": without_front_matter(text)[:MAX_ARTIFACT]}


async def repo_list(platform: "Platform", run: "Run", args: dict[str, Any]) -> dict[str, Any]:
    client, entry, _, _ = _target(platform, run, args.get("repo"))
    path = str(args.get("path") or "").strip("/")
    entries = await _call(lambda: client.list_dir(path, args.get("ref")))
    return {"repo": entry["repo"], "path": path, "entries": entries[:300]}


async def repo_read_file(platform: "Platform", run: "Run", args: dict[str, Any]) -> dict[str, Any]:
    client, entry, _, _ = _target(platform, run, args.get("repo"))
    path = str(args.get("path") or "")
    content = await _call(lambda: client.read_file(path, args.get("ref")))
    return {"repo": entry["repo"], "path": path, "content": content[:100_000], "truncated": len(content) > 100_000}


async def repo_pull_requests(platform: "Platform", run: "Run", args: dict[str, Any]) -> dict[str, Any]:
    client, entry, _, _ = _target(platform, run, args.get("repo"))
    found = await _call(client.open_pull_requests)
    return {
        "repo": entry["repo"],
        "pull_requests": [
            {"number": p.number, "title": p.title, "url": p.url, "branch": p.branch, "author": p.author} for p in found
        ],
    }


# Writing --------------------------------------------------------------------------------------------------------


async def plan_open_pull_request(platform: "Platform", run: "Run", args: dict[str, Any]) -> dict[str, Any]:
    """The plan for one target repository as `plan-<repo>.md`, by pull request from `sdlc/<id>/plan-<repo>` into the
    feature's branch on the control repository; only for an approved design, and never twice."""
    control_id = _check_id(args.get("control_id"))
    control = _control(platform, run)
    _, entry, _, _ = _target(platform, run, args.get("repo"))

    def open_it() -> dict[str, Any]:
        base = control.home(control_id)
        return open_plan(
            control,
            control_id,
            entry["repo"],
            args.get("content"),
            team=run.team,
            title=str(args.get("title") or f"{control_id}: plan for {entry['repo']}"),
            description=str(args.get("description") or ""),
            footer=f"Proposed by ci_workflow_agent for team {run.team} ({control_id}). Merging this pull request "
            f"into {base} approves the plan and starts the implementation in {entry['repo']} (DEC-0015).",
            record={"run_id": run.run_id},
        )

    return await _call(open_it)


async def workspace_run(platform: "Platform", run: "Run", args: dict[str, Any]) -> dict[str, Any]:
    """Applies a change set to `sdlc/<id>/<repo>` (from the feature branch the first time), runs the repository's
    declared setup, build and test commands in the Code Workspace and pushes the branch; returns each step's exit
    code and the end of its log. Only for an approved plan, within the run's limit of executions."""
    if platform.workspace is None:
        raise ToolError("unavailable", "the Code Workspace is not available in this environment")
    from event_agent_mcp.workspace import execute
    from event_agent_mcp.workspace import used as executions_used

    control_id = _check_id(args.get("control_id"))
    changes = await _call(lambda: check_changes(args.get("changes")))
    message = str(args.get("message") or f"{control_id}: implementation")[:500]
    control = _control(platform, run)
    _, entry, config, base_url = _target(platform, run, args.get("repo"))
    kind = plan_kind(entry["repo"])
    await _call(lambda: require_approved(control, control_id, kind))
    limit = int(run.limits.get("workspace_runs", 5))
    used = executions_used(platform.settings.store_root, run.run_id)
    if used >= limit:
        raise ToolError("limit_reached", f"this run may use the Code Workspace {limit} times; stop and comment instead")
    branch = implementation_branch(control_id, entry["repo"])
    commands = {k: v for k, v in (entry.get("workspace") or {}).items() if k in ("setup", "build", "test")}
    request = {
        "repo": entry["repo"],
        "provider": entry["provider"],
        "clone_url": clone_url(config.get("system", ""), config.get("edition", ""), base_url, entry["repo"]),
        "base": feature_branch(control_id),
        "start": entry.get("default_branch", "main"),
        "branch": branch,
        "changes": changes,
        "message": message,
        "commands": commands,
    }
    result = await execute(platform.workspace, platform.settings.store_root, run.run_id, request)
    steps = [{**s, "log_tail": str(s.get("log_tail") or "")[-MAX_LOG:]} for s in result.get("steps") or ()]
    if result.get("pushed"):
        results = {
            "repo": entry["repo"],
            "branch": branch,
            "commit": result.get("commit"),
            "ok": bool(result.get("ok")),
        }
        await _call(
            lambda: control.record(
                control_id,
                {"action": "workspace_push", "system": "repositories", "run_id": run.run_id, "results": results},
            )
        )
    return {
        "repo": entry["repo"],
        "branch": branch,
        "ok": bool(result.get("ok")),
        "pushed": bool(result.get("pushed")),
        "commit": result.get("commit"),
        "steps": steps,
        "built": bool(commands),
        "error": result.get("error"),
        "runs_left": limit - used - 1,
    }


async def implementation_open_pull_request(platform: "Platform", run: "Run", args: dict[str, Any]) -> dict[str, Any]:
    """The implementation pull request from `sdlc/<id>/<repo>` (pushed by workspace_run) into the feature's branch on
    the target repository, tagged with the Jira keys and linking the design and the plan; only for an approved plan,
    and never twice."""
    control_id = _check_id(args.get("control_id"))
    control = _control(platform, run)
    client, entry, _, _ = _target(platform, run, args.get("repo"))
    base = feature_branch(control_id)

    def open_it() -> dict[str, Any]:
        return open_implementation(
            control,
            client,
            entry,
            control_id,
            title=str(args.get("title") or f"{control_id}: implementation"),
            description=str(args.get("description") or ""),
            footer=f"Implemented by ci_workflow_agent for team {run.team} on "
            f"{control.settings['repo']}. A person reviews and merges this pull request "  # type: ignore[attr-defined]
            f"into {base}; the agent never merges.",
            record={"run_id": run.run_id},
        )

    return await _call(open_it)


async def pull_request_comment(platform: "Platform", run: "Run", args: dict[str, Any]) -> dict[str, Any]:
    """A comment on one of the feature's pull requests: its design or plan pull requests on the control repository
    (repo `control`), or a pull request from its `sdlc/` branch on a target repository. Used to report what blocks
    the run instead of guessing."""
    control_id = _check_id(args.get("control_id"))
    body = args.get("body")
    number = args.get("number")
    if not isinstance(body, str) or not body.strip() or len(body) > 20_000:
        raise ToolError("invalid_argument", "body is the comment's Markdown (at most 20,000 characters)")
    if not isinstance(number, int) or number < 1:
        raise ToolError("invalid_argument", "number is the pull request's number")
    control = _control(platform, run)
    target = args.get("repo")
    prefix = f"sdlc/{control_id}/"

    def comment() -> dict[str, Any]:
        if target == "control":
            client, repo = control.client, control.settings["repo"]  # type: ignore[attr-defined]
            allowed = {p["number"] for p in control.open_pull_requests() if p["branch"].startswith(prefix)}
            links = control.links(control_id)
            kinds = ["design", *(plan_kind(r) for r in _targets(links))]
            allowed |= {
                f.get("pull_request") for k in kinds if (f := control.approval(control_id, k)).get("pull_request")
            }
        else:
            client, entry, _, _ = _target(platform, run, target)
            repo = entry["repo"]
            allowed = {p.number for p in client.open_pull_requests() if p.branch.startswith(prefix)}
        if number not in allowed:
            raise ToolError("constraint_denied", f"pull request {number} on {repo} is not one of {control_id}'s")
        text = f"{body.strip()}\n\n_ci_workflow_agent, run {run.run_id}_"
        url = client.comment(number, text)
        control.record(
            control_id,
            {
                "action": "comment",
                "system": "control" if target == "control" else "repositories",
                "run_id": run.run_id,
                "results": {"repo": repo, "pull_request": number, "url": url},
            },
        )
        return {"repo": repo, "pull_request": number, "url": url}

    return await _call(comment)


CONTROL = {"type": "string", "pattern": CONTROL_ID.pattern, "description": "The feature's control ID."}
REPO = {"type": "string", "minLength": 1, "maxLength": 200, "description": "One of the team's repositories."}
REF = {"type": "string", "minLength": 1, "maxLength": 200, "description": "Branch or commit; default the main one."}

TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool(
            "feature_status",
            "The feature's artifacts and approvals on its branch, each target's plan, Jira keys and writes.",
            _schema({"control_id": CONTROL, "include_content": {"type": "boolean"}}, ("control_id",)),
            feature_status,
        ),
        Tool(
            "control_read_file",
            "Read one file of the feature's folder on its branch, such as design.md or plan-<repo>.md.",
            _schema(
                {"control_id": CONTROL, "file": {"type": "string", "pattern": FILE.pattern}}, ("control_id", "file")
            ),
            control_read_file,
        ),
        Tool(
            "repo_list",
            "List a folder of one of the team's repositories.",
            _schema({"repo": REPO, "path": {"type": "string", "maxLength": 500}, "ref": REF}, ("repo",)),
            repo_list,
        ),
        Tool(
            "repo_read_file",
            "Read a file of one of the team's repositories.",
            _schema(
                {"repo": REPO, "path": {"type": "string", "minLength": 1, "maxLength": 500}, "ref": REF},
                ("repo", "path"),
            ),
            repo_read_file,
        ),
        Tool(
            "repo_pull_requests",
            "The open pull requests of one of the team's repositories.",
            _schema({"repo": REPO}, ("repo",)),
            repo_pull_requests,
        ),
        Tool(
            "plan_open_pull_request",
            "Propose plan-<repo>.md for one target repository by pull request into the feature's branch on the control "
            "repository. Only for an approved design; an open one is returned instead of a second.",
            _schema(
                {
                    "control_id": CONTROL,
                    "repo": REPO,
                    "content": {"type": "string", "minLength": 1, "maxLength": MAX_ARTIFACT},
                    "title": {"type": "string", "maxLength": 200},
                    "description": {"type": "string", "maxLength": 20_000},
                },
                ("control_id", "repo", "content"),
            ),
            plan_open_pull_request,
            write=True,
        ),
        Tool(
            "workspace_run",
            "Apply whole-file changes to the implementation branch, run the repository's setup, build and tests in the "
            "Code Workspace and push the branch. Only for an approved plan; limited per run.",
            _schema(
                {
                    "control_id": CONTROL,
                    "repo": REPO,
                    "changes": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": MAX_CHANGES,
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "minLength": 1, "maxLength": 500},
                                "content": {"type": "string", "maxLength": MAX_FILE},
                                "delete": {"type": "boolean"},
                            },
                            "required": ["path"],
                            "additionalProperties": False,
                        },
                    },
                    "message": {"type": "string", "maxLength": 500},
                },
                ("control_id", "repo", "changes"),
            ),
            workspace_run,
            write=True,
        ),
        Tool(
            "implementation_open_pull_request",
            "Open the implementation pull request from the pushed implementation branch into the feature's branch on "
            "the target repository, with the Jira keys. Only for an approved plan; an open one is returned instead.",
            _schema(
                {
                    "control_id": CONTROL,
                    "repo": REPO,
                    "title": {"type": "string", "maxLength": 200},
                    "description": {"type": "string", "maxLength": 20_000},
                },
                ("control_id", "repo"),
            ),
            implementation_open_pull_request,
            write=True,
        ),
        Tool(
            "pull_request_comment",
            "Comment on one of the feature's pull requests (repo `control` for the control repository), for example "
            "to say what blocks the run.",
            _schema(
                {
                    "control_id": CONTROL,
                    "repo": REPO,
                    "number": {"type": "integer", "minimum": 1},
                    "body": {"type": "string", "minLength": 1, "maxLength": 20_000},
                },
                ("control_id", "repo", "number", "body"),
            ),
            pull_request_comment,
            write=True,
        ),
    )
}
