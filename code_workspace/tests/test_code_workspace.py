"""The Code Workspace against a local bare repository: checkout, change, build and test, push to the sdlc/ branch only,
and no token for the repository's own commands (DEC-0015); and the user mode, which only builds an archive the server
fetched (DEC-0016)."""

import io
import json
import os
import subprocess
import sys
import tarfile

import pytest
from code_workspace.__main__ import main
from code_workspace.run import execute, execute_request

TOKEN = "ghp_system-token-not-for-builds"
ENV = {**os.environ, "SYSTEM_TOKEN_GITHUB": TOKEN}
PY = f'"{sys.executable}"'


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def remote(tmp_path):
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git is not available")
    bare, seed = tmp_path / "remote.git", tmp_path / "seed"
    git(tmp_path, "init", "-q", "--bare", str(bare))
    seed.mkdir()
    git(seed, "init", "-q", "-b", "main")
    (seed / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(seed, "add", ".")
    git(seed, "-c", "user.name=t", "-c", "user.email=t@example.test", "commit", "-q", "-m", "seed")
    git(seed, "push", "-q", str(bare), "main", "main:feature/F-20261126-x")
    return bare


def request(remote, **overrides):
    return {
        "repo": "org/app",
        "provider": "github",
        "clone_url": remote.as_uri(),
        "base": "feature/F-20261126-x",
        "start": "main",
        "branch": "sdlc/F-20261126-x/app",
        "changes": [{"path": "pkg/refunds.py", "content": "def refund():\n    return 2\n"}],
        "message": "F-20261126-x: refunds",
        "commands": {"test": [f'{PY} -c "import pkg.refunds as r; assert r.refund() == 2"']},
        **overrides,
    }


def test_a_change_is_built_tested_and_pushed_to_its_sdlc_branch(remote):
    result = execute(request(remote), ENV)
    assert result["ok"] and result["pushed"] and result["steps"][0]["exit_code"] == 0, result
    assert git(remote, "rev-parse", "sdlc/F-20261126-x/app") == result["commit"]
    assert git(remote, "rev-parse", "feature/F-20261126-x") != result["commit"]  # the feature branch is untouched
    # the next execution continues from the pushed branch
    again = execute(request(remote, changes=[{"path": "app.py", "delete": True}], commands={}), ENV)
    assert again["pushed"] and git(remote, "show", "sdlc/F-20261126-x/app:pkg/refunds.py").startswith("def refund")
    files = git(remote, "ls-tree", "-r", "--name-only", "sdlc/F-20261126-x/app").split()
    assert files == ["pkg/refunds.py"]


def test_a_failing_test_is_a_result_not_an_error(remote):
    failing = {"test": [f"{PY} -c \"import sys; print('boom'); sys.exit(3)\"", f'{PY} -c "print(1)"']}
    result = execute(request(remote, commands=failing), ENV)
    assert not result["ok"] and result["pushed"]  # pushed so the agent can fix it on the same branch
    assert [s["exit_code"] for s in result["steps"]] == [3] and "boom" in result["steps"][0]["log_tail"]


def test_the_repositorys_commands_never_see_the_token(remote):
    check = "import os, sys; sys.exit(any(k.startswith(('SYSTEM_TOKEN', 'GIT_CONFIG')) for k in os.environ))"
    leak = f'{PY} -c "{check}"'
    result = execute(request(remote, commands={"test": [leak]}), ENV)
    assert result["ok"], result["steps"]
    assert TOKEN not in json.dumps(result)


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"branch": "feature/F-20261126-x"}, "only an sdlc/ branch"),
        ({"branch": "main"}, "only an sdlc/ branch"),
        ({"changes": [{"path": "../outside.py", "content": "x"}]}, "not a path inside"),
        ({"changes": [{"path": ".git/hooks/pre-commit", "content": "x"}]}, "not a path inside"),
        ({"provider": "gitlab"}, "no system connection"),
    ],
)
def test_refusals(remote, overrides, error):
    result = execute(request(remote, **overrides), ENV)
    assert not result["ok"] and not result["pushed"] and error in result["error"]


def test_no_token_no_run(remote):
    result = execute(request(remote), {k: v for k, v in ENV.items() if k != "SYSTEM_TOKEN_GITHUB"})
    assert result["error"] == "no system connection for this provider"


def test_the_job_reads_its_request_from_the_mount(remote, tmp_path, monkeypatch):
    folder = tmp_path / "mount" / "artifacts" / "system" / "runs" / "d-1_ci_implement" / "workspace-1"
    folder.mkdir(parents=True)
    (folder / "request.json").write_text(json.dumps(request(remote, commands={})), encoding="utf-8")
    monkeypatch.setenv("SYSTEM_TOKEN_GITHUB", TOKEN)
    monkeypatch.setenv("STORE_MOUNT_PATH", str(tmp_path / "mount"))
    monkeypatch.setenv("REQUEST_PATH", "artifacts/system/runs/d-1_ci_implement/workspace-1")
    assert main() == 0
    assert json.loads((folder / "result.json").read_text(encoding="utf-8"))["pushed"] is True
    monkeypatch.setenv("REQUEST_PATH", "../../etc")
    assert main() == 2
    assert execute_request(folder / "request.json", ENV)["pushed"] is False  # nothing new to push


def archive(files: dict[str, str]) -> bytes:
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as tar:
        for name, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(f"org-app-abc/{name}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return out.getvalue()


def user_folder(tmp_path, files, **request_overrides):
    folder = tmp_path / "mount" / "artifacts" / "users" / "u1" / "runs" / "F-20261126-x_app" / "workspace-1"
    folder.mkdir(parents=True)
    (folder / "source.tar.gz").write_bytes(archive(files))
    req = {
        "archive": "source.tar.gz",
        "changes": [{"path": "pkg/refunds.py", "content": "def refund():\n    return 2\n"}],
        "commands": {"test": [f'{PY} -c "import pkg.refunds as r, app; assert r.refund() == 2 and app.VALUE == 1"']},
        **request_overrides,
    }
    (folder / "request.json").write_text(json.dumps(req), encoding="utf-8")
    return folder


def test_user_mode_builds_the_archive_with_the_change_and_pushes_nothing(tmp_path, monkeypatch):
    folder = user_folder(tmp_path, {"app.py": "VALUE = 1\n"})
    monkeypatch.setenv("STORE_MOUNT_PATH", str(tmp_path / "mount"))
    monkeypatch.setenv("WORKSPACE_MODE", "user")
    monkeypatch.delenv("SYSTEM_TOKEN_GITHUB", raising=False)
    monkeypatch.setenv("REQUEST_PATH", "artifacts/users/u1/runs/F-20261126-x_app/workspace-1")
    assert main() == 0
    result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
    assert result["ok"] is True and result["pushed"] is False and result["steps"][0]["exit_code"] == 0
    monkeypatch.setenv("REQUEST_PATH", "artifacts/system/runs/d-1/workspace-1")  # not the user job's prefix
    assert main() == 2


def test_user_mode_refuses_a_missing_or_unsafe_archive(tmp_path):
    folder = user_folder(tmp_path, {"app.py": "VALUE = 1\n"}, archive="../secrets.tar.gz")
    env = {"WORKSPACE_MODE": "user", "PATH": os.environ.get("PATH", "")}
    assert "no repository archive" in execute_request(folder / "request.json", env)["error"]
    evil = io.BytesIO()
    with tarfile.open(fileobj=evil, mode="w:gz") as tar:
        info = tarfile.TarInfo("../escape.txt")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    (folder / "source.tar.gz").write_bytes(evil.getvalue())
    request_doc = json.loads((folder / "request.json").read_text(encoding="utf-8"))
    (folder / "request.json").write_text(json.dumps({**request_doc, "archive": "source.tar.gz"}), encoding="utf-8")
    result = execute_request(folder / "request.json", env)
    assert result["ok"] is False and "cannot be unpacked" in result["error"]
    assert not (tmp_path / "mount" / "artifacts" / "users" / "u1" / "runs" / "escape.txt").exists()
