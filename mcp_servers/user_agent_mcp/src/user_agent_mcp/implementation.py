"""The implementation plan and the implementation, with the user (DEC-0016, FR-SDLC-006).

Both are made as the user, with the user's own connections, on the run's team's repositories:

- `plan_publish`: `plan-<repo>.md` by pull request into the feature's branch on the control repository, only for a
  design a person merged. A person merging it approves the plan.
- `workspace_build`: the change built and tested in the credential-free Code Workspace job. This server fetches the
  repository's archive with the user's connection (the implementation branch if it exists, else the feature
  branch) and writes it with the request under `artifacts/user-runs/<user-id>/`; the job never reaches a
  repository.
- `implementation_publish`: the change committed to `sdlc/<id>/<repo>` with the user's connection and opened as a
  pull request into the target repository's feature branch, only for a plan a person merged. Where the repository
  declares build or test commands, the same change must have passed `workspace_build` first.

The rules shared with the unattended path (branch names, approvals, no second pull request, the record in
links.yaml) are libs/sdlc_control's.
"""

import hashlib
import json
from typing import TYPE_CHECKING, Any

from sdlc_connectors import ConnectorError
from sdlc_control import (
    ControlError,
    check_changes,
    feature_branch,
    implementation_branch,
    open_implementation,
    open_plan,
    plan_kind,
    require_approved,
)
from sdlc_workspace import WorkspaceFailed, executions
from sdlc_workspace import execute as run_workspace

from user_agent_mcp.control import Control, _check_id
from user_agent_mcp.errors import ToolError

if TYPE_CHECKING:
    from user_agent_mcp.platform import Caller, Platform

MAX_BUILDS = 20  # workspace builds per user, feature and repository
MAX_LOG = 4_000
ARCHIVE = "source.tar.gz"
COMMANDS = ("setup", "build", "test")


async def _run[T](fn) -> T:
    import asyncio

    try:
        return await asyncio.to_thread(fn)
    except ConnectorError as exc:
        raise ToolError(f"downstream_{exc.code}", exc.message) from exc
    except ControlError as exc:
        raise ToolError(exc.code, exc.message) from exc


def _checked_changes(value: Any) -> list[dict[str, Any]]:
    try:
        return check_changes(value)
    except ControlError as exc:
        raise ToolError(exc.code, exc.message) from exc


def changes_hash(changes: list[dict[str, Any]]) -> str:
    return hashlib.sha256(json.dumps(changes, sort_keys=True).encode()).hexdigest()


def _target(platform: "Platform", caller: "Caller", name: Any):
    from user_agent_mcp.systems import _repo

    if not isinstance(name, str) or not name:
        raise ToolError("invalid_argument", "name the target repository (owner/name)")
    return _repo(platform, caller, name, write=True)


def _prefix(caller: "Caller") -> str:
    return f"artifacts/user-runs/{caller.identity.user_id}"


def _run_id(control_id: str, repo: str) -> str:
    return f"{control_id}_{repo.rsplit('/', 1)[-1]}"


def _commands(repo: dict[str, Any]) -> dict[str, list[str]]:
    return {k: v for k, v in (repo.get("workspace") or {}).items() if k in COMMANDS and v}


async def plan_publish(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    control_id = _check_id(args.get("control_id"))
    control = Control(platform, caller)
    _, repo = _target(platform, caller, args.get("repo"))

    def publish() -> dict[str, Any]:
        base = control.home(control_id)
        return open_plan(
            control,
            control_id,
            repo["repo"],
            args.get("content"),
            team=control.team,
            title=str(args.get("title") or f"{control_id}: plan for {repo['repo']}"),
            description=str(args.get("description") or ""),
            footer=f"Published by {control.by} for team {control.team} ({control_id}, plan for {repo['repo']}). "
            f"Merging this pull request into {base} approves the plan for implementation (DEC-0016).",
        )

    out = await _run(publish)
    out["next"] = "a person merges the plan's pull request; then implement it with workspace_build"
    return out


async def workspace_build(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    if platform.workspace is None:
        raise ToolError("unavailable", "the Code Workspace is not available in this environment")
    control_id = _check_id(args.get("control_id"))
    changes = _checked_changes(args.get("changes"))
    control = Control(platform, caller)
    client, repo = _target(platform, caller, args.get("repo"))
    await _run(lambda: require_approved(control, control_id, plan_kind(repo["repo"])))
    commands = _commands(repo)
    digest = changes_hash(changes)
    if not commands:
        return {
            "repo": repo["repo"],
            "built": False,
            "ok": True,
            "changes_hash": digest,
            "note": "the repository declares no build or test commands: its own CI proves the change",
        }
    run_id, prefix = _run_id(control_id, repo["repo"]), _prefix(caller)
    used = len(executions(platform.settings.store_root, prefix, run_id))
    if used >= MAX_BUILDS:
        raise ToolError("limit_reached", f"{MAX_BUILDS} builds of this change already; ask the user how to go on")
    if not hasattr(client, "archive"):
        raise ToolError("not_supported", "building a change here needs a GitHub repository for now")
    branch, base = implementation_branch(control_id, repo["repo"]), feature_branch(control_id)

    def fetch() -> tuple[str, bytes]:
        for ref in (branch, base, repo.get("default_branch", "main")):
            if ref == repo.get("default_branch", "main") or client.branches(ref):
                return ref, client.archive(ref)
        raise ControlError("not_found", f"{repo['repo']} has none of {branch}, {base}")

    ref, archive = await _run(fetch)
    request = {"archive": ARCHIVE, "changes": changes, "commands": commands, "changes_hash": digest, "ref": ref}
    try:
        result = await run_workspace(
            platform.workspace, platform.settings.store_root, prefix, run_id, request, {ARCHIVE: archive}
        )
    except WorkspaceFailed as exc:
        raise ToolError(exc.code, exc.message) from exc
    steps = [{**s, "log_tail": str(s.get("log_tail") or "")[-MAX_LOG:]} for s in result.get("steps") or ()]
    return {
        "repo": repo["repo"],
        "built": True,
        "ok": bool(result.get("ok")),
        "ref": ref,
        "steps": steps,
        "error": result.get("error"),
        "changes_hash": digest,
        "builds_left": MAX_BUILDS - used - 1,
    }


def _last_build(platform: "Platform", caller: "Caller", control_id: str, repo: str) -> dict[str, Any] | None:
    found = executions(platform.settings.store_root, _prefix(caller), _run_id(control_id, repo))
    for folder in reversed(found):
        request, result = folder / "request.json", folder / "result.json"
        if request.is_file() and result.is_file():
            return {
                "changes_hash": json.loads(request.read_text(encoding="utf-8")).get("changes_hash"),
                "ok": bool(json.loads(result.read_text(encoding="utf-8")).get("ok")),
            }
    return None


async def implementation_publish(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    control_id = _check_id(args.get("control_id"))
    changes = _checked_changes(args.get("changes"))
    control = Control(platform, caller)
    client, repo = _target(platform, caller, args.get("repo"))
    if not hasattr(client, "commit_changes"):
        raise ToolError("not_supported", "committing a change here needs a GitHub repository for now")
    if _commands(repo):
        last = _last_build(platform, caller, control_id, repo["repo"])
        if last is None or last["changes_hash"] != changes_hash(changes):
            raise ToolError("not_built", "build this exact change with workspace_build first")
        if not last["ok"]:
            raise ToolError("not_built", "the last build of this change failed: fix it and build it again")
    branch, base = implementation_branch(control_id, repo["repo"]), feature_branch(control_id)
    message = str(args.get("message") or f"{control_id}: implementation")[:500]

    def publish() -> dict[str, Any]:
        require_approved(control, control_id, plan_kind(repo["repo"]))
        client.create_branch(base, repo.get("default_branch", "main"))  # opened with the feature; kept if it exists
        commit = client.commit_changes(branch, base, changes, message)
        out = open_implementation(
            control,
            client,
            repo,
            control_id,
            title=str(args.get("title") or f"{control_id}: implementation"),
            description=str(args.get("description") or ""),
            footer=f"Implemented with {control.by} in chat for team {control.team} (DEC-0016). A person reviews and "
            f"merges this pull request into {base}.",
        )
        return {**out, "commit": commit}

    return await _run(publish)
