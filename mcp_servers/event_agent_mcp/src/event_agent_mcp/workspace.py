"""Starting the system Code Workspace (DEC-0015, FR-SDLC-006), through libs/sdlc_workspace.

A request is written under `artifacts/system/runs/<run-id>/workspace-<n>/` of the artifact bucket; the job clones,
applies the change set, runs the declared commands, pushes the `sdlc/` branch with the machine user's token and
writes `result.json` next to it. Only this server starts the system job, and only for an approved plan.

Request: {repo, clone_url, provider, base, start, branch, changes: [{path, content} | {path, delete: true}], message,
commands: {setup, build, test}}. Result: {ok, steps: [{name, command, exit_code, seconds, log_tail}], commit,
pushed, error?}.
"""

from pathlib import Path
from typing import Any

from sdlc_workspace import JobRunner, LocalRunner, WorkspaceFailed, WorkspaceRunner, executions
from sdlc_workspace import execute as _execute

from event_agent_mcp.errors import ToolError

PREFIX = "artifacts/system/runs"

__all__ = ["PREFIX", "JobRunner", "LocalRunner", "WorkspaceRunner", "execute", "used"]


def used(store_root: Path, run_id: str) -> int:
    try:
        return len(executions(store_root, PREFIX, run_id))
    except WorkspaceFailed as exc:
        raise ToolError(exc.code, exc.message) from exc


async def execute(runner: WorkspaceRunner, store_root: Path, run_id: str, request: dict[str, Any]) -> dict[str, Any]:
    """Writes the request, runs the job and returns its result."""
    try:
        return await _execute(runner, store_root, PREFIX, run_id, request)
    except WorkspaceFailed as exc:
        raise ToolError(exc.code, exc.message) from exc
