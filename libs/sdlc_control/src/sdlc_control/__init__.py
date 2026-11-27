"""A team's sdlc-control repository (DEC-0012, DEC-0013, DEC-0015; FR-SDLC-001, FR-SDLC-013), shared by
user_agent_mcp (as the user) and event_agent_mcp (as the system identity).

A feature lives on its own branch, `feature/<control-id>`: `features/<control-id>/feature.md` (approved in chat, the
approval in its front matter), `design.md` and one `plan-<repo>.md` per target repository (each approved by a person
merging its pull request into the feature branch), and `links.yaml`, the record of every write made from them.
Features published before DEC-0013 live on the main branch, where a merge into main approves.

Which repository is the team's, and with whose connection it is reached, is the caller's business; this module only
knows the layout and the rules. A merge by one of the repository's system accounts (machine users) never approves.
"""

import re
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import yaml
from sdlc_connectors import Change, ConnectorError, FileChange

CONTROL_ID = re.compile(r"^F-[0-9]{8}-[a-z0-9][a-z0-9-]{0,39}$")
REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
# Branches pull requests come from: `sdlc/<id>/design-<hex>` (user_agent_mcp) and `sdlc/<id>/plan-<repo>`
# (ci_workflow_agent, one per target repository).
BRANCH = re.compile(
    r"^sdlc/(?P<control_id>F-[0-9]{8}-[a-z0-9-]{1,40})/"
    r"(?:(?P<kind>feature|design)-|plan-(?P<repo>[A-Za-z0-9_.-]{1,100})$)"
)
KINDS = ("feature", "design")
MAX_ARTIFACT = 200_000
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n?", re.S)


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def plan_kind(repo: str) -> str:
    """The artifact kind of the plan for one target repository: `plan-<name>` (the part after the owner)."""
    name = repo.rsplit("/", 1)[-1]
    if not REPO_NAME.match(name):
        raise ValueError(f"not a repository name: {repo!r}")
    return f"plan-{name}"


def path_of(control_id: str, kind: str) -> str:
    return f"features/{control_id}/{kind}.md"


def links_path(control_id: str) -> str:
    return f"features/{control_id}/links.yaml"


def feature_branch(control_id: str) -> str:
    return f"feature/{control_id}"


def front_matter(text: str) -> dict[str, Any]:
    match = FRONT_MATTER.match(text.lstrip())
    try:
        meta = yaml.safe_load(match.group(1)) if match else None
    except yaml.YAMLError:
        meta = None
    return meta if isinstance(meta, dict) else {}


def without_front_matter(text: str) -> str:
    return FRONT_MATTER.sub("", text.lstrip(), count=1).lstrip("\n")


def with_front_matter(body: str, meta: dict[str, Any]) -> str:
    return "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True) + "---\n\n" + body.strip() + "\n"


def branch_parts(branch: str) -> dict[str, str]:
    """The control ID and artifact kind a pull request's source branch names, or nothing."""
    match = BRANCH.match(branch)
    if not match:
        return {}
    return {"control_id": match["control_id"], "kind": match["kind"] or f"plan-{match['repo']}"}


class ControlRepository:
    """One team's control repository through a repository connector (`sdlc_connectors.repository`)."""

    def __init__(self, client: Any, branch: str = "main", system_accounts: Iterable[str] = (), by: str = ""):
        self.client, self.branch, self.by = client, branch, by
        self.system_accounts = {a.lower() for a in system_accounts}
        self._homes: dict[str, str] = {}

    def home(self, control_id: str) -> str:
        """The branch a feature's artifacts live on: its feature branch, or main for a feature published before
        DEC-0013."""
        if control_id not in self._homes:
            branch = feature_branch(control_id)
            self._homes[control_id] = branch if branch in self.client.branches(branch) else self.branch
        return self._homes[control_id]

    def on_feature_branch(self, control_id: str) -> bool:
        return self.home(control_id) != self.branch

    def approval(self, control_id: str, kind: str) -> dict[str, Any]:
        """Whether an artifact is approved on the feature's branch, and by whom: a feature by the user in chat (its
        front matter), anything else by a pull request into that branch merged by a person."""
        branch, path = self.home(control_id), path_of(control_id, kind)
        change: Change | None = self.client.last_change(path, branch)
        if change is None:
            return {"path": path, "branch": branch, "published": False, "approved": False}
        found: dict[str, Any] = {"path": path, "branch": branch, "published": True, "commit": change.commit}
        if kind == "feature" and branch != self.branch:
            meta = front_matter(self.read(path, branch) or "")
            approved = bool(meta.get("approved_by"))
            found |= {
                "approved": approved,
                "approved_by": meta.get("approved_by"),
                "approved_at": meta.get("approved_at"),
            }
            if not approved:
                found["reason"] = "the feature has no recorded approval"
            return found
        by_person = bool(change.merged_by) and change.merged_by.lower() not in self.system_accounts
        found["approved"] = bool(change.pull_request) and by_person
        if change.pull_request:
            found |= {"pull_request": change.pull_request, "merged_by": change.merged_by, "url": change.url}
            if not by_person:
                found["reason"] = f"merged by a system account ({change.merged_by}), not a person"
        else:
            found["reason"] = f"the last change on {branch} did not come from a merged pull request"
        return found

    def read(self, path: str, branch: str | None = None) -> str | None:
        try:
            return self.client.read_file(path, branch or self.branch)
        except ConnectorError as exc:
            if exc.code == "not_found":
                return None
            raise

    def links(self, control_id: str) -> dict[str, Any]:
        text = self.read(links_path(control_id), self.home(control_id))
        doc = yaml.safe_load(text) if text else None
        return doc if isinstance(doc, dict) else {"writes": []}

    def record(self, control_id: str, entry: dict[str, Any]) -> None:
        """Adds one write and its results to the feature's links.yaml, committed directly on the feature's branch."""
        doc = self.links(control_id)
        doc.setdefault("writes", []).append({"at": now(), "by": self.by, **entry})
        text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
        self.client.commit_file(
            links_path(control_id), text, self.home(control_id), f"{control_id}: record {entry['action']}"
        )

    def open_pull_requests(self) -> list[dict[str, Any]]:
        """The open pull requests, with the control ID and artifact kind their branch names."""
        return [
            {
                "number": pr.number,
                "title": pr.title,
                "url": pr.url,
                "branch": pr.branch,
                "author": pr.author,
                **branch_parts(pr.branch),
            }
            for pr in self.client.open_pull_requests()
        ]


# Plans and implementations: the rules both servers follow (DEC-0015 as the system identity, DEC-0016 as the user) --

PATH = re.compile(r"^[A-Za-z0-9_.@+-]+(/[A-Za-z0-9_.@+-]+)*$")
MAX_CHANGES, MAX_FILE, MAX_TOTAL = 200, 500_000, 5_000_000


class ControlError(Exception):
    """A rule of the control repository refused the step; each server reports it as its own tool error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


def jira_keys(links: dict[str, Any]) -> list[str]:
    """The Jira keys the feature's writes created (its feature and stories), in order."""
    keys: list[str] = []
    for write in links.get("writes") or ():
        results = write.get("results") or {}
        for key in [results.get("feature"), *(results.get("stories") or ())]:
            if isinstance(key, str) and key not in keys:
                keys.append(key)
    return keys


def targets(links: dict[str, Any]) -> list[str]:
    """The target repositories the feature's branch was opened on (feature_target_branches)."""
    found: list[str] = []
    for write in links.get("writes") or ():
        if write.get("action") == "open_branches":
            found += [r for r in (write.get("results") or {}) if r != "branch" and r not in found]
    return found


def title_with_keys(keys: list[str], text: str) -> str:
    head = " ".join(keys[:5])
    return (f"{head} {text}" if head and head not in text else text)[:200]


def implementation_branch(control_id: str, repo: str) -> str:
    """`sdlc/<control-id>/<repo name>`: the only branch an implementation is pushed to."""
    return f"sdlc/{control_id}/{repo.rsplit('/', 1)[-1]}"


def check_changes(value: Any) -> list[dict[str, Any]]:
    """Whole-file changes, [{path, content} | {path, delete: true}], inside the repository and within the limits."""
    if not isinstance(value, list) or not value or len(value) > MAX_CHANGES:
        raise ControlError("invalid_argument", f"changes is a list of 1 to {MAX_CHANGES} file changes")
    out, total = [], 0
    for change in value:
        path = change.get("path") if isinstance(change, dict) else None
        if not isinstance(path, str) or not PATH.match(path) or ".." in path.split("/") or path.startswith(".git/"):
            raise ControlError("invalid_argument", "each change names a relative path inside the repository")
        if change.get("delete") is True:
            out.append({"path": path, "delete": True})
            continue
        content = change.get("content")
        if not isinstance(content, str) or len(content) > MAX_FILE:
            raise ControlError("invalid_argument", f"{path}: content is the whole file (at most {MAX_FILE} characters)")
        total += len(content)
        out.append({"path": path, "content": content})
    if total > MAX_TOTAL:
        raise ControlError("invalid_argument", "the changes are too large for one run")
    return out


def require_feature_branch(control: ControlRepository, control_id: str) -> str:
    base = control.home(control_id)
    if base == control.branch:
        raise ControlError("not_found", f"{control_id} has no feature branch: plans and implementations need one")
    return base


def require_approved(control: ControlRepository, control_id: str, kind: str) -> dict[str, Any]:
    found = control.approval(control_id, kind)
    if not found["approved"]:
        reason = found.get("reason") or "not published"
        raise ControlError("not_approved", f"{kind}.md of {control_id} is not approved on {found['branch']}: {reason}")
    return found


def open_plan(
    control: ControlRepository,
    control_id: str,
    repo: str,
    content: Any,
    *,
    team: str,
    title: str,
    description: str,
    footer: str,
    record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """`plan-<repo>.md` by pull request from `sdlc/<id>/plan-<repo>` into the feature's branch on the control
    repository: only for a design a person merged, never for an approved plan, and an open one is returned instead
    of a second. The plan's front matter is written here, never by the model."""
    if not isinstance(content, str) or not content.strip() or len(content) > MAX_ARTIFACT:
        raise ControlError("invalid_argument", "content is the plan's Markdown (at most 200,000 characters)")
    kind = plan_kind(repo)
    base = require_feature_branch(control, control_id)
    design = require_approved(control, control_id, "design")
    if control.approval(control_id, kind)["approved"]:
        raise ControlError("already_done", f"{kind}.md of {control_id} is approved already")
    branch = f"sdlc/{control_id}/{kind}"
    for pr in control.open_pull_requests():
        if pr.get("control_id") == control_id and pr.get("kind") == kind:
            return {"control_id": control_id, "repo": repo, "already_open": True, "pull_request": pr}
    if control.client.branches(branch):
        raise ControlError("conflict", f"{branch} exists without an open pull request; a person deletes it to re-plan")
    keys = jira_keys(control.links(control_id))
    meta = {
        "control_id": control_id,
        "kind": "plan",
        "repo": repo,
        "team": team,
        "drafted_by": control.by,
        "published": now(),
        "previous": {"path": design["path"], "commit": design.get("commit"), "merged_by": design.get("merged_by")},
        **({"jira": keys} if keys else {}),
    }
    body = f"{description[:20_000]}\n\n---\n{footer}".strip()
    change = FileChange(path_of(control_id, kind), with_front_matter(without_front_matter(content), meta))
    pr = control.client.open_pull_request(
        branch, base, title_with_keys(keys, title), body, [change], f"{control_id}: plan for {repo}"
    )
    results = {"repo": repo, "pull_request": pr.number, "url": pr.url, "branch": branch}
    entry = {"action": "plan_pull_request", "system": "control", **(record or {}), "results": results}
    control.record(control_id, entry)
    return {"control_id": control_id, "repo": repo, "pull_request": {**results, "base": base}}


def open_implementation(
    control: ControlRepository,
    client: Any,
    repo: dict[str, Any],
    control_id: str,
    *,
    title: str,
    description: str,
    footer: str,
    record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The implementation pull request from `sdlc/<id>/<repo>` (already pushed) into the feature's branch on the
    target repository, tagged with the Jira keys: only for a plan a person merged, and an open one is returned
    instead of a second."""
    kind = plan_kind(repo["repo"])
    branch, base = implementation_branch(control_id, repo["repo"]), feature_branch(control_id)
    plan = require_approved(control, control_id, kind)
    design = control.approval(control_id, "design")
    if not client.branches(branch):
        raise ControlError("not_found", f"{branch} is not on {repo['repo']}: build and push the change first")
    for pr in client.open_pull_requests():
        if pr.branch == branch:
            found = {"number": pr.number, "url": pr.url, "branch": pr.branch}
            return {"control_id": control_id, "repo": repo["repo"], "already_open": True, "pull_request": found}
    client.create_branch(base, repo.get("default_branch", "main"))  # opened with the feature; kept if it exists
    keys = jira_keys(control.links(control_id))
    links = (
        f"From the approved plan ({plan.get('url') or plan['path']}) and design "
        f"({design.get('url') or design['path']}) of {control_id}."
    )
    body = f"{description[:20_000]}\n\n---\n{links}\n{footer}".strip()
    pr = client.create_pull_request(branch, base, title_with_keys(keys, title), body)
    results = {"repo": repo["repo"], "pull_request": pr.number, "url": pr.url, "branch": branch, "base": base}
    entry = {"action": "implementation_pull_request", "system": "repositories", **(record or {}), "results": results}
    control.record(control_id, entry)
    return {"control_id": control_id, "repo": repo["repo"], "pull_request": results, "jira_keys": keys}
