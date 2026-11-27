"""One execution of the Code Workspace (DEC-0015, DEC-0016, FR-SDLC-006).

Two modes, chosen by the job's own `WORKSPACE_MODE`, never by the request:

- `system` (the default; the job `code-workspace`, for event_agent_mcp): described below.
- `user` (the job `code-workspace-user`, for user_agent_mcp): the request folder holds the repository's archive,
  fetched by user_agent_mcp with the user's connection. The job unpacks it, applies the change set, runs the declared
  commands and writes `result.json`. It has no token and no git remote, and pushes nothing: user_agent_mcp commits
  the change with the user's connection afterwards.

System mode reads `request.json` (written by event_agent_mcp), checks out the implementation branch (or the feature
branch, the first time), applies the change set, commits it, runs the repository's declared setup, build and test
commands in order, pushes the branch, and writes `result.json` next to the request. It starts clean and keeps nothing.

- Only an `sdlc/` branch is ever pushed, never the feature branch or a protected one.
- The token (`SYSTEM_TOKEN_<PROVIDER>`, from Secret Manager) reaches git only as an HTTP header through git's
  environment; the repository's own commands run without it or any other platform variable.
- Change paths stay inside the repository and never touch `.git`.
"""

import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any

from sdlc_connectors import git_authorization

STEPS = ("setup", "build", "test")
LOG_TAIL = 4_000
BRANCH = re.compile(r"^sdlc/[A-Za-z0-9._/-]{1,200}$")
BASE = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")
# What the repository's own commands may see: nothing of the platform's.
SAFE_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "PYTHONUNBUFFERED", "CI", "SYSTEMROOT", "COMSPEC", "PATHEXT")
PROVIDERS = {  # provider -> (system, edition), as in config/providers.yaml
    "github": ("github", "cloud"),
    "github_enterprise": ("github", "data_center"),
    "bitbucket_cloud": ("bitbucket", "cloud"),
    "bitbucket_dc": ("bitbucket", "data_center"),
}


class WorkspaceError(Exception):
    pass


def token_variable(provider: str) -> str:
    return "SYSTEM_TOKEN_" + re.sub(r"[^A-Za-z0-9]", "_", provider).upper()


def _git(args: list[str], cwd: Path, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess:
    done = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
    if check and done.returncode != 0:
        # git's own message names the ref or path, never the header; the token is not in any argument
        raise WorkspaceError(f"git {args[0]} failed: {done.stderr.strip()[-500:]}")
    return done


def _inside(repo: Path, path: str) -> Path:
    parts = PurePosixPath(path).parts
    if not path or path.startswith("/") or ".." in parts or (parts and parts[0] == ".git") or "\\" in path:
        raise WorkspaceError(f"not a path inside the repository: {path!r}")
    target = (repo / path).resolve()
    if not target.is_relative_to(repo.resolve()):
        raise WorkspaceError(f"not a path inside the repository: {path!r}")
    return target


def apply_changes(repo: Path, changes: list[dict[str, Any]]) -> None:
    for change in changes:
        target = _inside(repo, str(change.get("path") or ""))
        if change.get("delete"):
            if target.is_file():
                target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(change.get("content") or ""), encoding="utf-8")


def run_steps(repo: Path, commands: dict[str, list[str]], deadline: float) -> list[dict[str, Any]]:
    """The declared commands, in order; the first that fails (or runs out of time) stops the rest."""
    env = {k: v for k, v in os.environ.items() if k in SAFE_ENV} | {"CI": "true"}
    steps = []
    for name in STEPS:
        for command in commands.get(name) or ():
            left = deadline - time.monotonic()
            started = time.monotonic()
            try:
                done = subprocess.run(
                    command, shell=True, cwd=repo, env=env, capture_output=True, text=True, timeout=max(left, 1)
                )
                code, output = done.returncode, (done.stdout or "") + (done.stderr or "")
            except subprocess.TimeoutExpired as exc:
                code, output = 124, f"{exc.stdout or ''}{exc.stderr or ''}\n(timed out)"
            steps.append(
                {
                    "name": name,
                    "command": command,
                    "exit_code": code,
                    "seconds": round(time.monotonic() - started, 1),
                    "log_tail": str(output)[-LOG_TAIL:],
                }
            )
            if code != 0:
                return steps
    return steps


def execute(request: dict[str, Any], environ: dict[str, str] | None = None, timeout: float = 1100) -> dict[str, Any]:
    """Runs one request; returns the result (never raises for a failing build or test)."""
    e = os.environ if environ is None else environ
    deadline = time.monotonic() + timeout
    branch, base, start = request.get("branch", ""), request.get("base", ""), request.get("start", "main")
    if not BRANCH.match(branch) or ".." in branch:
        return {"ok": False, "pushed": False, "steps": [], "error": "only an sdlc/ branch may be pushed"}
    if not BASE.match(base) or not BASE.match(start):
        return {"ok": False, "pushed": False, "steps": [], "error": "not a branch name"}
    system, edition = PROVIDERS.get(request.get("provider", ""), ("", ""))
    token = e.get(token_variable(request.get("provider", "")))
    if not system or not token:
        return {"ok": False, "pushed": False, "steps": [], "error": "no system connection for this provider"}
    git_env = {
        **{k: v for k, v in e.items() if k in ("SYSTEMROOT", "COMSPEC")},
        "PATH": e.get("PATH", os.defpath),
        "HOME": tempfile.gettempdir(),
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.extraHeader",
        "GIT_CONFIG_VALUE_0": git_authorization(system, edition, token),
        "GIT_AUTHOR_NAME": e.get("WORKSPACE_GIT_NAME", "ci_workflow_agent"),
        "GIT_AUTHOR_EMAIL": e.get("WORKSPACE_GIT_EMAIL", "ci-workflow-agent@users.noreply.example"),
    }
    git_env |= {"GIT_COMMITTER_NAME": git_env["GIT_AUTHOR_NAME"], "GIT_COMMITTER_EMAIL": git_env["GIT_AUTHOR_EMAIL"]}
    work = Path(tempfile.mkdtemp(prefix="workspace-"))
    repo = work / "repo"
    repo.mkdir()
    try:
        _git(["init", "-q"], repo, git_env)
        _git(["remote", "add", "origin", request["clone_url"]], repo, git_env)
        # the implementation branch if it was pushed before, else the feature branch, else the default branch
        for ref in (branch, base, start):
            if _git(["fetch", "-q", "origin", ref], repo, git_env, check=False).returncode == 0:
                break
        else:
            return {"ok": False, "pushed": False, "steps": [], "error": f"none of {branch}, {base}, {start} exists"}
        _git(["checkout", "-q", "-B", "work", "FETCH_HEAD"], repo, git_env)
        apply_changes(repo, request.get("changes") or [])
        _git(["add", "-A"], repo, git_env)
        changed = _git(["diff", "--cached", "--quiet"], repo, git_env, check=False).returncode != 0
        if changed:
            _git(["commit", "-q", "-m", str(request.get("message") or "implementation")[:500]], repo, git_env)
        commit = _git(["rev-parse", "HEAD"], repo, git_env).stdout.strip()
        steps = run_steps(repo, request.get("commands") or {}, deadline)
        ok = all(s["exit_code"] == 0 for s in steps)
        pushed = False
        if changed:
            _git(["push", "-q", "origin", f"HEAD:refs/heads/{branch}"], repo, git_env)
            pushed = True
        return {"ok": ok, "pushed": pushed, "commit": commit, "steps": steps, "changed": changed}
    except WorkspaceError as exc:
        return {"ok": False, "pushed": False, "steps": [], "error": str(exc)}
    finally:
        shutil.rmtree(work, ignore_errors=True)


ARCHIVE = re.compile(r"^[A-Za-z0-9_.-]{1,100}\.tar\.gz$")


def _unpack(archive: Path, into: Path) -> Path:
    """The archive's files under `into`, safely (no links out, no absolute paths, no devices); returns the
    repository's root, the archive's single top-level folder when it has one (as GitHub's do)."""
    with tarfile.open(archive, mode="r:gz") as tar:
        tar.extractall(into, filter="data")
    entries = [p for p in into.iterdir()]
    return entries[0] if len(entries) == 1 and entries[0].is_dir() else into


def execute_user(request: dict[str, Any], folder: Path, timeout: float = 1100) -> dict[str, Any]:
    """User mode: builds and tests the change on the archive the server fetched; never reaches a repository."""
    deadline = time.monotonic() + timeout
    name = str(request.get("archive") or "")
    if not ARCHIVE.match(name) or not (folder / name).is_file():
        return {"ok": False, "pushed": False, "steps": [], "error": "the request has no repository archive"}
    work = Path(tempfile.mkdtemp(prefix="workspace-"))
    try:
        try:
            repo = _unpack(folder / name, work / "src")
        except (tarfile.TarError, OSError) as exc:
            return {"ok": False, "pushed": False, "steps": [], "error": f"the archive cannot be unpacked: {exc}"}
        apply_changes(repo, request.get("changes") or [])
        steps = run_steps(repo, request.get("commands") or {}, deadline)
        return {"ok": all(s["exit_code"] == 0 for s in steps), "pushed": False, "steps": steps}
    except WorkspaceError as exc:
        return {"ok": False, "pushed": False, "steps": [], "error": str(exc)}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def execute_request(request_path: Path, environ: dict[str, str] | None = None) -> dict[str, Any]:
    """Reads request.json, runs it in the job's mode and writes result.json next to it."""
    e = os.environ if environ is None else environ
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    timeout = float(e.get("WORKSPACE_TIMEOUT_SECONDS", "1100"))
    mode = e.get("WORKSPACE_MODE", "system")
    if mode == "user":
        result = execute_user(request, Path(request_path).parent, timeout)
    elif mode == "system":
        result = execute(request, environ, timeout)
    else:
        result = {"ok": False, "pushed": False, "steps": [], "error": f"unknown WORKSPACE_MODE {mode!r}"}
    (Path(request_path).parent / "result.json").write_text(json.dumps(result), encoding="utf-8")
    return result
