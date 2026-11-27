"""In-memory fakes of the providers' APIs, for the tests of the components that use the connectors."""

import base64
import json

import httpx


class FakeGitHub:
    """A GitHub repository in memory, with branches: a pull request copies its head branch into its base on
    `merge`; a PUT on a branch is a direct commit. Use `handle` as an httpx.MockTransport handler for the API base
    path `/repos/<owner>/<name>`."""

    def __init__(self, base: str):
        self.BASE = base
        self.trees: dict[str, dict[str, str]] = {"main": {}}
        self.how: dict[tuple[str, str], tuple[int | None, str | None]] = {}
        self.prs: dict[int, dict] = {}
        self.merged: set[int] = set()
        self.merged_by: dict[int, str] = {}
        self.comments: dict[int, list[str]] = {}
        self.starts: dict[str, dict[str, str]] = {}  # each branch's tree when it was created

    def merge(self, number: int, by: str = "grace") -> None:
        pr = self.prs[number]
        self.merged.add(number)
        self.merged_by[number] = by
        start = self.starts.get(pr["head"], {})
        for path, content in self.trees[pr["head"]].items():
            if start.get(path) == content:  # unchanged on the branch: the base keeps its own (a three-way merge)
                continue
            if self.trees[pr["base"]].get(path) != content:
                self.trees[pr["base"]][path] = content
                self.how[(pr["base"], path)] = (number, by)

    def push(self, branch: str, path: str, content: str) -> None:
        self.trees.setdefault(branch, {})[path] = content
        self.how[(branch, path)] = (None, None)

    def file(self, branch: str, path: str) -> str:
        return self.trees[branch][path]

    def handle(self, request: httpx.Request) -> httpx.Response:
        path, method, params = request.url.path[len(self.BASE) :], request.method, dict(request.url.params)
        if method == "GET" and path.startswith("/git/matching-refs/heads/"):
            prefix = path[len("/git/matching-refs/heads/") :]
            return httpx.Response(200, json=[{"ref": f"refs/heads/{b}"} for b in self.trees if b.startswith(prefix)])
        if method == "GET" and path.startswith("/git/ref/heads/"):
            name = path[len("/git/ref/heads/") :]
            return (
                httpx.Response(200, json={"object": {"sha": f"head:{name}"}})
                if name in self.trees
                else httpx.Response(404)
            )
        if method == "POST" and path == "/git/refs":
            body = json.loads(request.content)
            name, start = body["ref"].removeprefix("refs/heads/"), dict(self.trees[body["sha"].removeprefix("head:")])
            self.trees[name], self.starts[name] = start, dict(start)
            return httpx.Response(201, json={})
        if method == "GET" and path == "/commits":
            branch, file = params.get("sha", "main"), params["path"]
            found = file in self.trees.get(branch, {})
            return httpx.Response(200, json=[{"sha": f"c|{branch}|{file}"}] if found else [])
        if method == "GET" and path.startswith("/commits/c|"):
            _, branch, file = path[len("/commits/") :].removesuffix("/pulls").split("|")
            number, _ = self.how.get((branch, file), (None, None))
            if number is None:
                return httpx.Response(200, json=[])
            pr = {"number": number, "merged_at": "t", "base": {"ref": branch}, "html_url": f"https://gh/pr/{number}"}
            return httpx.Response(200, json=[pr])
        if method == "GET" and path == "/pulls":
            return httpx.Response(
                200,
                json=[
                    {"number": n, "title": b["title"], "html_url": f"https://gh/pr/{n}", "head": {"ref": b["head"]}}
                    for n, b in self.prs.items()
                    if n not in self.merged
                ],
            )
        if method == "GET" and path.startswith("/pulls/"):
            number = int(path.rsplit("/", 1)[-1])
            by = self.merged_by.get(number) or next((b for n, b in self.how.values() if n == number), None)
            body = self.prs.get(number) or {}
            merged = number in self.merged or by is not None
            return httpx.Response(
                200,
                json={
                    "number": number,
                    "state": "closed" if merged else "open",
                    "merged": merged,
                    "merged_by": {"login": by} if by else None,
                    "merge_commit_sha": f"m{number}" if merged else None,
                    "base": {"ref": body.get("base", "")},
                    "head": {"ref": body.get("head", "")},
                    "html_url": f"https://gh/pr/{number}",
                },
            )
        if method == "POST" and path.startswith("/issues/") and path.endswith("/comments"):
            number = int(path.split("/")[2])
            self.comments.setdefault(number, []).append(json.loads(request.content)["body"])
            return httpx.Response(201, json={"html_url": f"https://gh/pr/{number}#comment"})
        if method == "POST" and path == "/pulls":
            body = json.loads(request.content)
            number = len(self.prs) + 1
            self.prs[number] = body
            return httpx.Response(201, json={"number": number, "html_url": f"https://gh/pr/{number}"})
        if path.startswith("/contents/"):
            file, ref = path[len("/contents/") :], params.get("ref", "main")
            if method == "GET":
                if file not in self.trees.get(ref, {}):
                    return httpx.Response(404)
                content = base64.b64encode(self.trees[ref][file].encode()).decode()
                return httpx.Response(200, json={"type": "file", "content": content, "sha": "s"})
            body = json.loads(request.content)
            self.push(body["branch"], file, base64.b64decode(body["content"]).decode())
            return httpx.Response(200, json={"commit": {"sha": "d"}})
        return httpx.Response(404)
