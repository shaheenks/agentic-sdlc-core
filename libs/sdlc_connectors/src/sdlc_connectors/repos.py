"""Repositories: GitHub (cloud and Enterprise Server) and Bitbucket (Cloud and Data Center), behind one interface.

Everything a design run needs: read a file or a folder, and open a pull request that adds files on a new branch.
Commits are made with the connection's own credential, so they are the connection owner's.
"""

import base64
import re
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from sdlc_connectors.base import ConnectorError, Credential, Http

BRANCH = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")
PATH = re.compile(r"^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$")


@dataclass(frozen=True)
class FileChange:
    path: str
    content: str


@dataclass(frozen=True)
class PullRequest:
    number: int
    url: str
    branch: str


class Repository(Protocol):
    def whoami(self) -> dict[str, Any]: ...
    def read_file(self, path: str, ref: str | None = None) -> str: ...
    def list_dir(self, path: str, ref: str | None = None) -> list[dict[str, str]]: ...
    def open_pull_request(
        self, branch: str, base: str, title: str, body: str, files: list[FileChange], message: str
    ) -> PullRequest: ...


def _check(path: str = "", branch: str = "") -> None:
    if path and not PATH.match(path):
        raise ConnectorError("invalid", "not a repository path")
    if branch and (not BRANCH.match(branch) or ".." in branch):
        raise ConnectorError("invalid", "not a branch name")


class GitHub:
    """GitHub.com (`https://api.github.com`) or Enterprise Server (`https://<host>/api/v3`)."""

    def __init__(self, base_url: str, repo: str, credential: Credential, client: httpx.Client | None = None):
        self.repo = repo
        headers = {"Authorization": f"Bearer {credential.token}", "X-GitHub-Api-Version": "2022-11-28"}
        self.http = Http(base_url, headers, "GitHub", client)

    def whoami(self) -> dict[str, Any]:
        me = self.http.request("GET", "/user")
        return {"account": me.get("login"), "name": me.get("name")}

    def read_file(self, path: str, ref: str | None = None) -> str:
        _check(path=path)
        found = self.http.request(
            "GET", f"/repos/{self.repo}/contents/{quote(path)}", params={"ref": ref} if ref else None
        )
        if not isinstance(found, dict) or found.get("type") != "file":
            raise ConnectorError("not_found", "not a file")
        return base64.b64decode(found.get("content") or "").decode("utf-8", errors="replace")

    def list_dir(self, path: str, ref: str | None = None) -> list[dict[str, str]]:
        _check(path=path)
        found = self.http.request(
            "GET", f"/repos/{self.repo}/contents/{quote(path)}", params={"ref": ref} if ref else None
        )
        if not isinstance(found, list):
            raise ConnectorError("not_found", "not a folder")
        return [{"name": f["name"], "path": f["path"], "type": "dir" if f["type"] == "dir" else "file"} for f in found]

    def open_pull_request(
        self, branch: str, base: str, title: str, body: str, files: list[FileChange], message: str
    ) -> PullRequest:
        _check(branch=branch)
        head = self.http.request("GET", f"/repos/{self.repo}/git/ref/heads/{quote(base)}")
        self.http.request(
            "POST", f"/repos/{self.repo}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": head["object"]["sha"]}
        )
        for change in files:
            _check(path=change.path)
            content = base64.b64encode(change.content.encode()).decode()
            self.http.request(
                "PUT",
                f"/repos/{self.repo}/contents/{quote(change.path)}",
                json={"message": message, "content": content, "branch": branch},
            )
        pr = self.http.request(
            "POST", f"/repos/{self.repo}/pulls", json={"title": title, "body": body, "head": branch, "base": base}
        )
        return PullRequest(pr["number"], pr["html_url"], branch)


class BitbucketCloud:
    """Bitbucket Cloud (`https://api.bitbucket.org`): an access token (bearer), or an app password with the
    username as the connection's account (basic)."""

    def __init__(self, base_url: str, repo: str, credential: Credential, client: httpx.Client | None = None):
        self.repo = repo
        if credential.account:
            basic = base64.b64encode(f"{credential.account}:{credential.token}".encode()).decode()
            auth = f"Basic {basic}"
        else:
            auth = f"Bearer {credential.token}"
        self.http = Http(base_url, {"Authorization": auth}, "Bitbucket", client)

    def whoami(self) -> dict[str, Any]:
        me = self.http.request("GET", "/2.0/user")
        return {"account": me.get("username") or me.get("nickname"), "name": me.get("display_name")}

    def _ref(self, ref: str | None) -> str:
        if ref:
            return ref
        return self.http.request("GET", f"/2.0/repositories/{self.repo}")["mainbranch"]["name"]

    def read_file(self, path: str, ref: str | None = None) -> str:
        _check(path=path)
        found = self.http.request("GET", f"/2.0/repositories/{self.repo}/src/{quote(self._ref(ref))}/{quote(path)}")
        if not isinstance(found, str):
            raise ConnectorError("not_found", "not a file")
        return found

    def list_dir(self, path: str, ref: str | None = None) -> list[dict[str, str]]:
        _check(path=path)
        found = self.http.request("GET", f"/2.0/repositories/{self.repo}/src/{quote(self._ref(ref))}/{quote(path)}/")
        values = (found or {}).get("values") if isinstance(found, dict) else None
        if values is None:
            raise ConnectorError("not_found", "not a folder")
        return [
            {
                "name": v["path"].rsplit("/", 1)[-1],
                "path": v["path"],
                "type": "dir" if v["type"] == "commit_directory" else "file",
            }
            for v in values
        ]

    def open_pull_request(
        self, branch: str, base: str, title: str, body: str, files: list[FileChange], message: str
    ) -> PullRequest:
        _check(branch=branch)
        for change in files:
            _check(path=change.path)
        # The src endpoint takes a form: each file's path names its content; one commit, on a new branch that
        # starts from the main branch's head.
        form = {change.path: change.content for change in files} | {"message": message, "branch": branch}
        self.http.request("POST", f"/2.0/repositories/{self.repo}/src", data=form)
        pr = self.http.request(
            "POST",
            f"/2.0/repositories/{self.repo}/pullrequests",
            json={
                "title": title,
                "description": body,
                "source": {"branch": {"name": branch}},
                "destination": {"branch": {"name": base}},
            },
        )
        return PullRequest(pr["id"], pr["links"]["html"]["href"], branch)


class BitbucketDataCenter:
    """Bitbucket Data Center (`https://<host>`), repository `PROJECT/slug`, with a personal access token."""

    def __init__(self, base_url: str, repo: str, credential: Credential, client: httpx.Client | None = None):
        project, _, slug = repo.partition("/")
        self.base = f"/rest/api/1.0/projects/{project}/repos/{slug}"
        self.project, self.slug = project, slug
        self.http = Http(base_url, {"Authorization": f"Bearer {credential.token}"}, "Bitbucket", client)

    def whoami(self) -> dict[str, Any]:
        # The application properties need no rights; a refused token fails here with 401.
        self.http.request("GET", "/rest/api/1.0/application-properties")
        return {"account": None, "name": None}

    def read_file(self, path: str, ref: str | None = None) -> str:
        _check(path=path)
        found = self.http.request("GET", f"{self.base}/raw/{quote(path)}", params={"at": ref} if ref else None)
        return found if isinstance(found, str) else str(found)

    def list_dir(self, path: str, ref: str | None = None) -> list[dict[str, str]]:
        _check(path=path)
        found = self.http.request("GET", f"{self.base}/browse/{quote(path)}", params={"at": ref} if ref else None)
        children = ((found or {}).get("children") or {}).get("values") or []
        return [
            {
                "name": c["path"]["toString"],
                "path": f"{path}/{c['path']['toString']}",
                "type": "dir" if c.get("type") == "DIRECTORY" else "file",
            }
            for c in children
        ]

    def open_pull_request(
        self, branch: str, base: str, title: str, body: str, files: list[FileChange], message: str
    ) -> PullRequest:
        _check(branch=branch)
        self.http.request("POST", f"{self.base}/branches", json={"name": branch, "startPoint": f"refs/heads/{base}"})
        for change in files:
            _check(path=change.path)
            self.http.request(
                "PUT",
                f"{self.base}/browse/{quote(change.path)}",
                files={"content": (None, change.content), "message": (None, message), "branch": (None, branch)},
            )
        repository = {"slug": self.slug, "project": {"key": self.project}}
        pr = self.http.request(
            "POST",
            f"{self.base}/pull-requests",
            json={
                "title": title,
                "description": body,
                "fromRef": {"id": f"refs/heads/{branch}", "repository": repository},
                "toRef": {"id": f"refs/heads/{base}", "repository": repository},
            },
        )
        return PullRequest(pr["id"], pr["links"]["self"][0]["href"], branch)


def repository(system: str, edition: str, base_url: str, repo: str, credential: Credential, client=None) -> Repository:
    if system == "github":
        return GitHub(base_url, repo, credential, client)
    if system == "bitbucket":
        cls = BitbucketCloud if edition == "cloud" else BitbucketDataCenter
        return cls(base_url, repo, credential, client)
    raise ValueError(f"not a repository system: {system!r}")
