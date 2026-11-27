"""Starting the Code Workspace and reading its result, for both MCP servers (DEC-0015, DEC-0016).

A request is written as `request.json` (with any input files, such as the repository archive of a user's run) under
`<prefix>/<run-id>/workspace-<n>/` of the artifact bucket, because it is too large for job overrides. The job reads
it from its own mount of the bucket, runs, and writes `result.json` next to it.

- event_agent_mcp: prefix `artifacts/system/runs`, the system job (it clones and pushes with the machine user's
  token).
- user_agent_mcp: prefix `artifacts/users/<user-id>/runs`, the credential-free job `code-workspace-user`. That job
  only unpacks the archive the server fetched with the user's connection, applies the changes and runs the declared
  commands; it never reaches a repository.
"""

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Protocol

import httpx

RUN_ID = re.compile(r"^[A-Za-z0-9._:-]{1,120}$")
PREFIX = re.compile(r"^artifacts/(system|users/[A-Za-z0-9_-]{1,128})/runs$")
FILE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
RUN_API = "https://run.googleapis.com/v2"
SYSTEM, USER = "system", "user"


class WorkspaceFailed(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


class WorkspaceRunner(Protocol):
    async def run(self, request_path: Path, relative: str) -> None: ...


def _runs(store_root: Path, prefix: str, run_id: str) -> Path:
    if not PREFIX.match(prefix):
        raise WorkspaceFailed("invalid_argument", "not a workspace folder")
    if not RUN_ID.match(run_id):
        raise WorkspaceFailed("invalid_argument", "the run ID is not usable as a folder name")
    return store_root / prefix / run_id.replace(":", "_")


def executions(store_root: Path, prefix: str, run_id: str) -> list[Path]:
    """The run's earlier executions, oldest first."""
    runs = _runs(store_root, prefix, run_id)
    found = [p for p in runs.iterdir() if p.name.startswith("workspace-")] if runs.is_dir() else []
    return sorted(found, key=lambda p: int(p.name.removeprefix("workspace-") or 0))


def request_folder(store_root: Path, prefix: str, run_id: str) -> tuple[Path, str]:
    """A new folder for one execution of the run: (absolute, relative to the bucket)."""
    runs = _runs(store_root, prefix, run_id)
    runs.mkdir(parents=True, exist_ok=True)
    n = 1 + len(executions(store_root, prefix, run_id))
    relative = f"{prefix}/{run_id.replace(':', '_')}/workspace-{n}"
    folder = store_root / relative
    folder.mkdir()
    return folder, relative


async def execute(
    runner: WorkspaceRunner,
    store_root: Path,
    prefix: str,
    run_id: str,
    request: dict[str, Any],
    files: dict[str, bytes] | None = None,
) -> dict[str, Any]:
    """Writes the request and its files, runs the job and returns its result."""
    folder, relative = request_folder(store_root, prefix, run_id)
    for name, data in (files or {}).items():
        if not FILE.match(name) or name in ("request.json", "result.json"):
            raise WorkspaceFailed("invalid_argument", "not a request file name")
        (folder / name).write_bytes(data)
    (folder / "request.json").write_text(json.dumps(request), encoding="utf-8")
    await runner.run(folder / "request.json", relative)
    result_path = folder / "result.json"
    if not result_path.is_file():
        raise WorkspaceFailed("workspace_failed", "the Code Workspace finished without a result")
    for name in files or {}:  # inputs are not kept once the job has run (the archive is the repository's code)
        (folder / name).unlink(missing_ok=True)
    return json.loads(result_path.read_text(encoding="utf-8"))


class JobRunner:
    """Runs a Code Workspace Cloud Run job with REQUEST_PATH set, and waits for its execution to finish."""

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
            raise WorkspaceFailed("workspace_failed", f"Cloud Run answered {response.status_code} starting the job")
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
                raise WorkspaceFailed("workspace_failed", "the Code Workspace did not finish in time")
            await asyncio.sleep(10)
            operation = await self._request("GET", f"{RUN_API}/{operation['name']}")
        if operation.get("error"):
            raise WorkspaceFailed("workspace_failed", "the Code Workspace execution failed to run")


class LocalRunner:
    """The local environment: the Code Workspace's own code, in this process (it must be installed). In user mode
    it runs without any SYSTEM_TOKEN_* variable, as the credential-free job does."""

    def __init__(self, mode: str = SYSTEM) -> None:
        self.mode = mode

    async def run(self, request_path: Path, relative: str) -> None:
        try:
            from code_workspace.run import execute_request
        except ImportError as exc:
            raise WorkspaceFailed("unavailable", "the Code Workspace is not installed here") from exc
        environ = None
        if self.mode == USER:
            environ = {k: v for k, v in os.environ.items() if not k.startswith("SYSTEM_TOKEN_")}
            environ["WORKSPACE_MODE"] = USER
        await asyncio.to_thread(execute_request, request_path, environ)
