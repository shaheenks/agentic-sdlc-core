"""Repositories: GitHub (cloud and Enterprise Server) and Bitbucket (Cloud and Data Center), behind one interface.

Everything a design run needs: read a file or a folder, and open a pull request that adds files on a new branch.
For a team's control repository (DEC-0012) also: the last change to a file on a branch, with the pull request it was
merged through and who merged it, and a direct commit of one file. Commits are made with the connection's own
credential, so they are the connection owner's.
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


@dataclass(frozen=True)
class Change:
    """The last commit that changed a file on a branch, and the merged pull request it came from, if any."""

    commit: str
    pull_request: int | None = None
    merged_by: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class OpenPullRequest:
    number: int
    title: str
    url: str
    branch: str
    author: str | None = None


class Repository(Protocol):
    def whoami(self) -> dict[str, Any]: ...
    def read_file(self, path: str, ref: str | None = None) -> str: ...
    def list_dir(self, path: str, ref: str | None = None) -> list[dict[str, str]]: ...
    def open_pull_request(
        self, branch: str, base: str, title: str, body: str, files: list[FileChange], message: str
    ) -> PullRequest: ...
    def last_change(self, path: str, branch: str) -> Change | None: ...
    def commit_file(self, path: str, content: str, branch: str, message: str) -> str: ...
    def open_pull_requests(self) -> list[OpenPullRequest]: ...
    def branches(self, prefix: str) -> list[str]: ...
    def create_branch(self, name: str, start: str) -> bool: ...
    def create_pull_request(self, branch: str, base: str, title: str, body: str) -> PullRequest: ...
    def comment(self, number: int, body: str) -> str: ...


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
            self._put(change.path, change.content, branch, message)
        return self.create_pull_request(branch, base, title, body)

    def create_pull_request(self, branch: str, base: str, title: str, body: str) -> PullRequest:
        """A pull request from an existing branch."""
        _check(branch=branch)
        _check(branch=base)
        pr = self.http.request(
            "POST", f"/repos/{self.repo}/pulls", json={"title": title, "body": body, "head": branch, "base": base}
        )
        return PullRequest(pr["number"], pr["html_url"], branch)

    def comment(self, number: int, body: str) -> str:
        """A comment on a pull request; returns its link."""
        done = self.http.request("POST", f"/repos/{self.repo}/issues/{int(number)}/comments", json={"body": body})
        return (done or {}).get("html_url", "")

    def _put(self, path: str, content: str, branch: str, message: str) -> str:
        """Creates or replaces one file on a branch; returns the commit."""
        _check(path=path, branch=branch)
        body = {"message": message, "content": base64.b64encode(content.encode()).decode(), "branch": branch}
        try:
            found = self.http.request("GET", f"/repos/{self.repo}/contents/{quote(path)}", params={"ref": branch})
            if isinstance(found, dict) and found.get("sha"):
                body["sha"] = found["sha"]
        except ConnectorError as exc:
            if exc.code != "not_found":
                raise
        done = self.http.request("PUT", f"/repos/{self.repo}/contents/{quote(path)}", json=body)
        return ((done or {}).get("commit") or {}).get("sha", "")

    def commit_file(self, path: str, content: str, branch: str, message: str) -> str:
        return self._put(path, content, branch, message)

    def branches(self, prefix: str) -> list[str]:
        """Branch names that start with `prefix`."""
        _check(branch=prefix.rstrip("/") or "x")
        found = self.http.request("GET", f"/repos/{self.repo}/git/matching-refs/heads/{quote(prefix)}") or []
        return [r["ref"].removeprefix("refs/heads/") for r in found if isinstance(r, dict) and "ref" in r]

    def create_branch(self, name: str, start: str) -> bool:
        """Creates `name` from the head of `start`; False when it exists already."""
        _check(branch=name)
        _check(branch=start)
        if name in self.branches(name):
            return False
        head = self.http.request("GET", f"/repos/{self.repo}/git/ref/heads/{quote(start)}")
        self.http.request(
            "POST", f"/repos/{self.repo}/git/refs", json={"ref": f"refs/heads/{name}", "sha": head["object"]["sha"]}
        )
        return True

    def open_pull_requests(self) -> list[OpenPullRequest]:
        found = self.http.request("GET", f"/repos/{self.repo}/pulls", params={"state": "open", "per_page": 100}) or []
        return [
            OpenPullRequest(
                p["number"],
                p.get("title", ""),
                p.get("html_url", ""),
                (p.get("head") or {}).get("ref", ""),
                (p.get("user") or {}).get("login"),
            )
            for p in found
        ]

    def last_change(self, path: str, branch: str) -> Change | None:
        _check(path=path, branch=branch)
        commits = self.http.request(
            "GET", f"/repos/{self.repo}/commits", params={"path": path, "sha": branch, "per_page": 1}
        )
        if not commits:
            return None
        sha = commits[0]["sha"]
        for pr in self.http.request("GET", f"/repos/{self.repo}/commits/{sha}/pulls") or ():
            if pr.get("merged_at") and (pr.get("base") or {}).get("ref") == branch:
                full = self.http.request("GET", f"/repos/{self.repo}/pulls/{pr['number']}")
                merged_by = (full.get("merged_by") or {}).get("login")
                return Change(sha, pr["number"], merged_by, pr.get("html_url"))
        return Change(sha)


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
        _check(branch=base)
        # The src endpoint takes a form: each file's path names its content; one commit, on a new branch that
        # starts from the base branch's head (`parents`).
        form = {change.path: change.content for change in files} | {
            "message": message,
            "branch": branch,
            "parents": base,
        }
        self.http.request("POST", f"/2.0/repositories/{self.repo}/src", data=form)
        return self.create_pull_request(branch, base, title, body)

    def create_pull_request(self, branch: str, base: str, title: str, body: str) -> PullRequest:
        """A pull request from an existing branch."""
        _check(branch=branch)
        _check(branch=base)
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

    def comment(self, number: int, body: str) -> str:
        """A comment on a pull request; returns its link."""
        done = self.http.request(
            "POST",
            f"/2.0/repositories/{self.repo}/pullrequests/{int(number)}/comments",
            json={"content": {"raw": body}},
        )
        return (((done or {}).get("links") or {}).get("html") or {}).get("href", "")

    def commit_file(self, path: str, content: str, branch: str, message: str) -> str:
        _check(path=path, branch=branch)
        self.http.request(
            "POST", f"/2.0/repositories/{self.repo}/src", data={path: content, "message": message, "branch": branch}
        )
        change = self.last_change(path, branch)
        return change.commit if change else ""

    def branches(self, prefix: str) -> list[str]:
        _check(branch=prefix.rstrip("/") or "x")
        found = self.http.request(
            "GET", f"/2.0/repositories/{self.repo}/refs/branches", params={"q": f'name ~ "{prefix}"', "pagelen": 100}
        )
        return [b["name"] for b in (found or {}).get("values") or () if str(b.get("name", "")).startswith(prefix)]

    def create_branch(self, name: str, start: str) -> bool:
        _check(branch=name)
        _check(branch=start)
        if name in self.branches(name):
            return False
        head = self.http.request("GET", f"/2.0/repositories/{self.repo}/refs/branches/{quote(start)}")
        self.http.request(
            "POST",
            f"/2.0/repositories/{self.repo}/refs/branches",
            json={"name": name, "target": {"hash": head["target"]["hash"]}},
        )
        return True

    def open_pull_requests(self) -> list[OpenPullRequest]:
        found = self.http.request(
            "GET", f"/2.0/repositories/{self.repo}/pullrequests", params={"state": "OPEN", "pagelen": 50}
        )
        return [
            OpenPullRequest(
                p["id"],
                p.get("title", ""),
                ((p.get("links") or {}).get("html") or {}).get("href", ""),
                ((p.get("source") or {}).get("branch") or {}).get("name", ""),
                (p.get("author") or {}).get("display_name"),
            )
            for p in (found or {}).get("values") or ()
        ]

    def last_change(self, path: str, branch: str) -> Change | None:
        _check(path=path, branch=branch)
        found = self.http.request(
            "GET", f"/2.0/repositories/{self.repo}/commits/{quote(branch)}", params={"path": path, "pagelen": 1}
        )
        values = (found or {}).get("values") or []
        if not values:
            return None
        sha = values[0]["hash"]
        prs = self.http.request("GET", f"/2.0/repositories/{self.repo}/commit/{sha}/pullrequests") or {}
        for pr in prs.get("values") or ():
            if (
                pr.get("state") == "MERGED"
                and ((pr.get("destination") or {}).get("branch") or {}).get("name") == branch
            ):
                full = self.http.request("GET", f"/2.0/repositories/{self.repo}/pullrequests/{pr['id']}")
                closed_by = full.get("closed_by") or {}
                merged_by = closed_by.get("nickname") or closed_by.get("display_name")
                return Change(sha, pr["id"], merged_by, ((pr.get("links") or {}).get("html") or {}).get("href"))
        return Change(sha)


class BitbucketDataCenter:
    """Bitbucket Data Center (`https://<host>`), repository `PROJECT/slug`, with a personal access token."""

    def __init__(self, base_url: str, repo: str, credential: Credential, client: httpx.Client | None = None):
        project, _, slug = repo.partition("/")
        self.base = f"/rest/api/1.0/projects/{project}/repos/{slug}"
        self.project, self.slug = project, slug
        self.web = f"{base_url.rstrip('/')}/projects/{project}/repos/{slug}"
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
            self._put(change.path, change.content, branch, message)
        return self.create_pull_request(branch, base, title, body)

    def create_pull_request(self, branch: str, base: str, title: str, body: str) -> PullRequest:
        """A pull request from an existing branch."""
        _check(branch=branch)
        _check(branch=base)
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

    def comment(self, number: int, body: str) -> str:
        """A comment on a pull request; returns its link."""
        done = self.http.request("POST", f"{self.base}/pull-requests/{int(number)}/comments", json={"text": body})
        return f"{self.web}/pull-requests/{int(number)}/overview?commentId={(done or {}).get('id', '')}"

    def _last_commit(self, path: str, branch: str) -> str | None:
        try:
            found = self.http.request("GET", f"{self.base}/commits", params={"path": path, "until": branch, "limit": 1})
        except ConnectorError as exc:
            if exc.code == "not_found":
                return None
            raise
        values = (found or {}).get("values") or []
        return values[0]["id"] if values else None

    def _put(self, path: str, content: str, branch: str, message: str) -> str:
        """Creates or replaces one file on a branch; replacing needs the file's last commit."""
        _check(path=path, branch=branch)
        form: dict[str, Any] = {"content": (None, content), "message": (None, message), "branch": (None, branch)}
        previous = self._last_commit(path, branch)
        if previous:
            form["sourceCommitId"] = (None, previous)
        done = self.http.request("PUT", f"{self.base}/browse/{quote(path)}", files=form)
        return (done or {}).get("id", "") if isinstance(done, dict) else ""

    def commit_file(self, path: str, content: str, branch: str, message: str) -> str:
        return self._put(path, content, branch, message)

    def branches(self, prefix: str) -> list[str]:
        _check(branch=prefix.rstrip("/") or "x")
        found = self.http.request("GET", f"{self.base}/branches", params={"filterText": prefix, "limit": 100})
        return [
            b["displayId"] for b in (found or {}).get("values") or () if str(b.get("displayId", "")).startswith(prefix)
        ]

    def create_branch(self, name: str, start: str) -> bool:
        _check(branch=name)
        _check(branch=start)
        if name in self.branches(name):
            return False
        self.http.request("POST", f"{self.base}/branches", json={"name": name, "startPoint": f"refs/heads/{start}"})
        return True

    def open_pull_requests(self) -> list[OpenPullRequest]:
        found = self.http.request("GET", f"{self.base}/pull-requests", params={"state": "OPEN", "limit": 100})
        return [
            OpenPullRequest(
                p["id"],
                p.get("title", ""),
                (((p.get("links") or {}).get("self") or [{}])[0]).get("href", ""),
                (p.get("fromRef") or {}).get("displayId", ""),
                ((p.get("author") or {}).get("user") or {}).get("name"),
            )
            for p in (found or {}).get("values") or ()
        ]

    def last_change(self, path: str, branch: str) -> Change | None:
        _check(path=path, branch=branch)
        sha = self._last_commit(path, branch)
        if not sha:
            return None
        prs = self.http.request("GET", f"{self.base}/commits/{sha}/pull-requests") or {}
        for pr in prs.get("values") or ():
            if pr.get("state") == "MERGED" and (pr.get("toRef") or {}).get("displayId") == branch:
                activities = self.http.request("GET", f"{self.base}/pull-requests/{pr['id']}/activities") or {}
                merged = next((a for a in activities.get("values") or () if a.get("action") == "MERGED"), {})
                merged_by = (merged.get("user") or {}).get("name")
                link = (((pr.get("links") or {}).get("self") or [{}])[0]).get("href")
                return Change(sha, pr["id"], merged_by, link)
        return Change(sha)


def repository(system: str, edition: str, base_url: str, repo: str, credential: Credential, client=None) -> Repository:
    if system == "github":
        return GitHub(base_url, repo, credential, client)
    if system == "bitbucket":
        cls = BitbucketCloud if edition == "cloud" else BitbucketDataCenter
        return cls(base_url, repo, credential, client)
    raise ValueError(f"not a repository system: {system!r}")


def clone_url(system: str, edition: str, base_url: str, repo: str) -> str:
    """The HTTPS URL git clones a repository from (the Code Workspace, DEC-0015): GitHub.com and Bitbucket Cloud by
    their web host, GitHub Enterprise Server without its `/api/v3`, Bitbucket Data Center under `/scm`."""
    if not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", repo):
        raise ValueError(f"not a repository: {repo!r}")
    base = base_url.rstrip("/")
    if system == "github":
        host = "https://github.com" if edition == "cloud" else base.removesuffix("/api/v3")
        return f"{host}/{repo}.git"
    if system == "bitbucket":
        if edition == "cloud":
            return f"https://bitbucket.org/{repo}.git"
        project, _, slug = repo.partition("/")
        return f"{base}/scm/{project.lower()}/{slug}.git"
    raise ValueError(f"not a repository system: {system!r}")
