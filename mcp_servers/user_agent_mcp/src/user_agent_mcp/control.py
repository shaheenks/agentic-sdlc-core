"""The run's team's control repository (DEC-0012, DEC-0013, FR-SDLC-001, FR-SDLC-013).

A feature the user approves in chat gets its own branch, `feature/<control-id>`, on the control repository: its
`feature.md` is committed there with the approval recorded in its front matter (who and when), and every later
artifact of the feature (design, plans) reaches that branch by a pull request a person merges. Every write to Jira,
Confluence or a product repository checks the approval on the feature's branch first and records its results in the
feature's `links.yaml` there afterwards. Features published before DEC-0013 live on the main branch, where the
DEC-0012 rule (merged into main) still applies.

The checks are made by this server, never by the agent: which repository is the team's (configuration), where an
artifact lives, its front matter (written here, not by the model), and whether it is approved.
"""

import re
import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import yaml
from sdlc_connectors import Change, ConnectorError, FileChange, repository

from user_agent_mcp.errors import ToolError

if TYPE_CHECKING:
    from user_agent_mcp.platform import Caller, Platform

CONTROL_ID = re.compile(r"^F-[0-9]{8}-[a-z0-9][a-z0-9-]{0,39}$")
BRANCH = re.compile(r"^sdlc/(F-[0-9]{8}-[a-z0-9-]{1,40})/(feature|design)-")
KINDS = ("feature", "design")
MAX_ARTIFACT = 200_000
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n?", re.S)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def path_of(control_id: str, kind: str) -> str:
    return f"features/{control_id}/{kind}.md"


def links_path(control_id: str) -> str:
    return f"features/{control_id}/links.yaml"


def feature_branch(control_id: str) -> str:
    return f"feature/{control_id}"


def _check_id(control_id: Any) -> str:
    if not isinstance(control_id, str) or not CONTROL_ID.match(control_id):
        raise ToolError("invalid_argument", "control_id looks like F-20261125-refunds")
    return control_id


class Control:
    """The run's team's control repository, reached with the user's own connection."""

    def __init__(self, platform: "Platform", caller: "Caller", write: bool = True):
        from user_agent_mcp.systems import _credential, _edition, _run_team, scope

        self.team = _run_team(caller)
        settings = (scope(caller).get(self.team) or {}).get("control_repo")
        if not settings:
            raise ToolError("constraint_denied", "your team has no control repository in this environment")
        system, edition = _edition(caller, settings["provider"])
        base_url = settings.get("base_url") or caller.bundle.config["providers"][settings["provider"]].get("base_url")
        self.settings, self.branch = settings, settings.get("branch", "main")
        self.system_accounts = {a.lower() for a in settings.get("system_accounts") or ()}
        self.client = repository(
            system, edition, base_url, settings["repo"], _credential(platform, caller, settings["provider"])
        )
        self.by = caller.identity.email
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
            meta = _front_matter(self.read(path, branch) or "")
            approved = bool(meta.get("approved_by"))
            found |= {
                "approved": approved,
                "approved_by": meta.get("approved_by"),
                "approved_at": meta.get("approved_at"),
            }
            if not approved:
                found["reason"] = "the feature has no recorded approval"
            return found
        approved = bool(
            change.pull_request and change.merged_by and change.merged_by.lower() not in self.system_accounts
        )
        found["approved"] = approved
        if change.pull_request:
            found |= {"pull_request": change.pull_request, "merged_by": change.merged_by, "url": change.url}
        else:
            found["reason"] = f"the last change on {branch} did not come from a merged pull request"
        return found

    def require_approved(self, control_id: str, kind: str) -> dict[str, Any]:
        found = self.approval(control_id, kind)
        if not found["approved"]:
            how = (
                "approve the feature in chat first (feature_open)"
                if kind == "feature"
                else f"open its pull request into {found['branch']} with control_publish and have it merged first"
            )
            raise ToolError("not_approved", f"{kind}.md of {control_id} is not approved: {how}")
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
        doc.setdefault("writes", []).append({"at": _now(), "by": self.by, **entry})
        text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
        self.client.commit_file(
            links_path(control_id), text, self.home(control_id), f"{control_id}: record {entry['action']}"
        )


def _front_matter(text: str) -> dict[str, Any]:
    match = FRONT_MATTER.match(text.lstrip())
    try:
        meta = yaml.safe_load(match.group(1)) if match else None
    except yaml.YAMLError:
        meta = None
    return meta if isinstance(meta, dict) else {}


def _open_pull_requests(control: "Control") -> list[dict[str, Any]]:
    """The control repository's open pull requests, with the control ID and kind their branch names."""
    found = []
    for pr in control.client.open_pull_requests():
        match = BRANCH.match(pr.branch)
        found.append(
            {
                "number": pr.number,
                "title": pr.title,
                "url": pr.url,
                "branch": pr.branch,
                "author": pr.author,
                **({"control_id": match.group(1), "kind": match.group(2)} if match else {}),
            }
        )
    return found


def _similar(open_prs: list[dict[str, Any]], kind: str, control_id: str | None, slug: str) -> dict[str, Any] | None:
    """An open pull request for the same artifact: the same control ID and kind, or, for an artifact without a
    control ID yet, a feature of the same name (any date)."""
    for pr in open_prs:
        if pr.get("kind") != kind:
            continue
        if control_id and pr.get("control_id") == control_id:
            return pr
        if not control_id and re.match(rf"^F-[0-9]{{8}}-{re.escape(slug)}(-[0-9]+)?$", pr.get("control_id", "")):
            return pr
    return None


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40].strip("-")
    return slug or "feature"


def _body(content: Any) -> str:
    if not isinstance(content, str) or not content.strip() or len(content) > MAX_ARTIFACT:
        raise ToolError("invalid_argument", "each artifact needs its Markdown text (at most 200,000 characters)")
    return FRONT_MATTER.sub("", content.lstrip(), count=1)


def _with_front_matter(body: str, meta: dict[str, Any]) -> str:
    return "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True) + "---\n\n" + body.strip() + "\n"


async def feature_open(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    """The feature the user approved in chat (DEC-0013): its branch `feature/<control-id>` on the control repository,
    with feature.md and the approval (who, when) committed to it as the user. A feature already open under the same
    control ID or name is returned instead; nothing is opened twice."""
    from user_agent_mcp.systems import _call

    control = Control(platform, caller)
    if args.get("control_id"):
        control_id = _check_id(args["control_id"])
        if not await _call(lambda: control.on_feature_branch(control_id)):
            raise ToolError("not_found", f"{control_id} has no feature branch")
        return {"control_id": control_id, "branch": feature_branch(control_id), "already_open": True}
    body = _body(args.get("content"))
    summary = str(args.get("summary") or body.splitlines()[0])
    slug = _slug(summary)
    named = re.compile(rf"^feature/(F-[0-9]{{8}}-{re.escape(slug)}(-[0-9]+)?)$")
    for branch in await _call(lambda: control.client.branches("feature/F-")):
        match = named.match(branch)
        if match:
            return {"control_id": match.group(1), "branch": branch, "already_open": True}
    control_id = await _new_id(control, summary)
    branch = feature_branch(control_id)
    meta = {
        "control_id": control_id,
        "team": control.team,
        "kind": "feature",
        "drafted_by": control.by,
        "approved_by": control.by,
        "approved_at": _now(),
        "approved_in": "chat",
        **({"epic": args["epic"]} if isinstance(args.get("epic"), str) and args["epic"] else {}),
    }
    await _call(lambda: control.client.create_branch(branch, control.branch))
    await _call(
        lambda: control.client.commit_file(
            path_of(control_id, "feature"),
            _with_front_matter(body, meta),
            branch,
            f"{control_id}: feature approved by {control.by} in chat",
        )
    )
    return {"control_id": control_id, "branch": branch, "files": [path_of(control_id, "feature")]}


async def feature_target_branches(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    """The approved feature's branch on the team's target repositories (its default when none is named), from each
    repository's default branch, recorded on the feature branch; an existing branch is left as it is."""
    from user_agent_mcp.systems import _call, _repo

    control = Control(platform, caller)
    control_id = _check_id(args.get("control_id"))
    await _call(lambda: control.require_approved(control_id, "feature"))
    names = [r for r in args.get("repositories") or [] if isinstance(r, str)][:10] or [None]
    branch, opened = feature_branch(control_id), {}
    for name in names:
        client, repo = _repo(platform, caller, name, write=True)
        created = await _call(lambda c=client, r=repo: c.create_branch(branch, r["default_branch"]))
        opened[repo["repo"]] = "created" if created else "existed"
    await _call(
        lambda: control.record(
            control_id, {"action": "open_branches", "system": "repositories", "results": {"branch": branch, **opened}}
        )
    )
    return {"control_id": control_id, "branch": branch, "repositories": opened}


async def control_publish(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    """Opens a pull request with a design into the feature's branch on the team's control repository, as the user;
    a person merging it approves it (DEC-0013). Features are approved in chat and opened with feature_open."""
    from user_agent_mcp.systems import _call

    control = Control(platform, caller)
    kind = args.get("kind")
    if kind == "feature":
        raise ToolError("invalid_argument", "a feature is approved in chat and opened with feature_open (DEC-0013)")
    if kind != "design":
        raise ToolError("invalid_argument", "kind must be design")
    body = _body(args.get("content"))
    control_id = _check_id(args.get("control_id"))
    jira = [k for k in args.get("jira_keys") or [] if isinstance(k, str)][:50]
    base = await _call(lambda: control.home(control_id))
    if base == control.branch:
        raise ToolError("not_found", f"{control_id} has no feature branch: approve the feature first (publish_feature)")
    existing = _similar(await _call(lambda: _open_pull_requests(control)), kind, control_id, "")
    if existing:
        return {
            "control_id": control_id,
            "kind": kind,
            "already_open": True,
            "pull_request": {"number": existing["number"], "url": existing["url"], "branch": existing["branch"]},
            "next": "a pull request for this is already open: have it merged (or closed) instead of opening another",
        }
    feature = await _call(lambda: control.approval(control_id, "feature"))
    meta = {
        "control_id": control_id,
        "kind": "design",
        "team": control.team,
        "drafted_by": control.by,
        "published": _now(),
        "previous": {"path": feature["path"], "commit": feature.get("commit"), "approved": feature["approved"]},
        **({"jira": jira} if jira else {}),
    }
    keys = " ".join(jira[:5])
    title = str(args.get("title") or f"{control_id}: design")[:200]
    if keys and keys not in title:
        title = f"{keys} {title}"[:200]
    description = str(args.get("description") or "")[:20_000]
    description += f"\n\n---\nPublished by {control.by} for team {control.team} ({control_id}, design). Merging this "
    description += f"pull request into {base} approves it (DEC-0013)."
    branch = f"sdlc/{control_id}/design-{secrets.token_hex(3)}"
    changes = [FileChange(path_of(control_id, "design"), _with_front_matter(body, meta))]
    pr = await _call(
        lambda: control.client.open_pull_request(
            branch, base, title, description.strip(), changes, f"{control_id}: design"
        )
    )
    return {
        "control_id": control_id,
        "kind": kind,
        "pull_request": {"number": pr.number, "url": pr.url, "branch": pr.branch, "base": base},
        "files": [path_of(control_id, "design")],
        "next": f"a person merges the pull request into {base}; then control_status shows the design as approved",
    }


async def _new_id(control: Control, summary: str) -> str:
    from user_agent_mcp.systems import _call

    base = f"F-{datetime.now(UTC):%Y%m%d}-{_slug(summary)}"
    for n in range(1, 20):
        candidate = base if n == 1 else f"{base[:46]}-{n}"
        taken = await _call(
            lambda c=candidate: (
                bool(control.client.branches(feature_branch(c)))
                or control.client.last_change(path_of(c, "feature"), control.branch) is not None
            )
        )
        if not taken:
            return candidate
    raise ToolError("conflict", "too many features with this name today; give a different summary")


async def control_status(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    """Whether a feature's artifacts are approved (on its feature branch), what has been written from them, and, on
    request, their text. Finds the feature by control ID or by the Jira key of its feature issue."""
    from user_agent_mcp.systems import _call

    control = Control(platform, caller)
    control_id = args.get("control_id")
    jira_key = args.get("jira_key")
    if not control_id and isinstance(jira_key, str):
        control_id = await _control_id_of(platform, caller, jira_key)
    control_id = _check_id(control_id)
    artifacts = {}
    for kind in KINDS:
        found = await _call(lambda k=kind: control.approval(control_id, k))
        if args.get("include_content") and found["published"]:
            text = await _call(lambda p=found["path"], b=found["branch"]: control.read(p, b))
            found["content"] = FRONT_MATTER.sub("", (text or "").lstrip(), count=1)[:MAX_ARTIFACT]
        artifacts[kind] = found
    links = await _call(lambda: control.links(control_id))
    result = {
        "control_id": control_id,
        "team": control.team,
        "repository": control.settings["repo"],
        "branch": control.home(control_id),
        "artifacts": artifacts,
        "writes": links.get("writes") or [],
    }
    if isinstance(jira_key, str):
        result["jira_feature_recorded"] = any(
            (w.get("results") or {}).get("feature") == jira_key for w in result["writes"]
        )
    return result


SDLC_LINK = re.compile(r"^sdlc-control (F-[0-9]{8}-[a-z0-9-]{1,40})$")


async def _control_id_of(platform: "Platform", caller: "Caller", key: str) -> str:
    """The control ID a Jira feature was created from: the link jira_create_feature put on it, checked against
    links.yaml by the caller (`jira_feature_recorded`)."""
    from user_agent_mcp.systems import _call, _jira, _jira_projects, _project_of

    allowed = _jira_projects(caller, write=True)
    project = _project_of(key, allowed)
    jira = _jira(platform, caller, allowed[project][1])
    for link in await _call(lambda: jira.remote_links(key)):
        match = SDLC_LINK.match(link.get("title") or "")
        if match:
            return match.group(1)
    raise ToolError("not_found", f"{key} was not created from the control repository (no sdlc-control link)")


async def control_pull_requests(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    """The open pull requests on the run's team's control repository, with the feature and artifact each is for."""
    from user_agent_mcp.systems import _call

    control = Control(platform, caller)
    return {"repository": control.settings["repo"], "pull_requests": await _call(lambda: _open_pull_requests(control))}
