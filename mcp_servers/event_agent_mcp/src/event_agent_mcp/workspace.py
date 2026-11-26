"""Starting the Code Workspace (DEC-0015, FR-SDLC-006).

A request is written as `request.json` under `artifacts/system/runs/<run-id>/workspace-<n>/` of the artifact bucket
(too large for job overrides); the job reads it from its own mount of the bucket, runs, and writes `result.json` next
to it. Only this server starts the job, and only for an approved plan.

Request: {repo, clone_url, provider, base, branch, changes: [{path, content} | {path, delete: true}], message,
commands: {setup, build, test}}. Result: {ok, steps: [{name, command, exit_code, seconds, log_tail}], commit,
pushed, error?}.
"""

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any, Protocol

import httpx

from event_agent_mcp.errors import ToolError

RUN_ID = re.compile(r"^[A-Za-z0-9._:-]{1,120}$")
RUN_API = "https://run.googleapis.com/v2"


class WorkspaceRunner(Protocol):
    async def run(self, request_path: Path, relative: str) -> None: ...


def request_folder(store_root: Path, run_id: str) -> tuple[Path, str]:
    """A new folder for one execution of the run: (absolute, relative to the bucket)."""
    if not RUN_ID.match(run_id):
        raise ToolError("invalid_argument", "the run ID is not usable as a folder name")
    safe = run_id.replace(":", "_")
    runs = store_root / "artifacts" / "system" / "runs" / safe
    runs.mkdir(parents=True, exist_ok=True)
    n = 1 + sum(1 for p in runs.iterdir() if p.name.startswith("workspace-"))
    relative = f"artifacts/system/runs/{safe}/workspace-{n}"
    folder = store_root / relative
    folder.mkdir()
    return folder, relative


async def execute(runner: WorkspaceRunner, store_root: Path, run_id: str, request: dict[str, Any]) -> dict[str, Any]:
    """Writes the request, runs the job and returns its result."""
    folder, relative = request_folder(store_root, run_id)
    (folder / "request.json").write_text(json.dumps(request), encoding="utf-8")
    await runner.run(folder / "request.json", relative)
    result_path = folder / "result.json"
    if not result_path.is_file():
        raise ToolError("workspace_failed", "the Code Workspace finished without a result")
    return json.loads(result_path.read_text(encoding="utf-8"))


class JobRunner:
    """Runs the Code Workspace Cloud Run job with REQUEST_PATH set, and waits for its execution to finish."""

    def __init__(self, job: str, timeout_seconds: int, client: httpx.AsyncClient | None = None, credentials=None):
        self.job, self.timeout = job, timeout_seconds
        self.client = client or httpx.AsyncClient(timeout=30)
        self._credentials = credentials

    async def _token(self) -> str:
        if self._credentials is None:
            import google.auth

            self._credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        if not self._credentials.valid:
            import google.auth.transport.requests

            await asyncio.to_thread(self._credentials.refresh, google.auth.transport.requests.Request())
        return self._credentials.token

    async def _request(self, method: str, url: str, **kwargs) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {await self._token()}"}
        response = await self.client.request(method, url, headers=headers, **kwargs)
        if response.status_code >= 400:
            raise ToolError("workspace_failed", f"Cloud Run answered {response.status_code} starting the job")
        return response.json()

    async def run(self, request_path: Path, relative: str) -> None:
        body = {
            "overrides": {
                "containerOverrides": [{"env": [{"name": "REQUEST_PATH", "value": relative}]}],
                "taskCount": 1,
                "timeout": f"{self.timeout}s",
            }
        }
        operation = await self._request("POST", f"{RUN_API}/{self.job}:run", json=body)
        deadline = time.monotonic() + self.timeout + 120
        while not operation.get("done"):
            if time.monotonic() > deadline:
                raise ToolError("workspace_failed", "the Code Workspace did not finish in time")
            await asyncio.sleep(10)
            operation = await self._request("GET", f"{RUN_API}/{operation['name']}")
        if operation.get("error"):
            raise ToolError("workspace_failed", "the Code Workspace execution failed to run")


class LocalRunner:
    """The local environment: the Code Workspace's own code, in this process (it must be installed)."""

    async def run(self, request_path: Path, relative: str) -> None:
        try:
            from code_workspace.run import execute_request
        except ImportError as exc:
            raise ToolError("unavailable", "the Code Workspace is not installed here") from exc
        await asyncio.to_thread(execute_request, request_path)
