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
from sdlc_connectors import Change, ConnectorError

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
