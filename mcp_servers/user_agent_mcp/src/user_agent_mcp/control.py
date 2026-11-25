"""The run's team's control repository (DEC-0012, FR-SDLC-001, FR-SDLC-013): artifacts are published there by pull
request with the user's own connection, a person merging the pull request approves them, and every write to Jira,
Confluence or a product repository checks that approval here first and records its results here afterwards.

The checks are made by this server, never by the agent: which repository is the team's (configuration), where an
artifact lives (`features/<control-id>/<kind>.md`), its front matter (written here, not by the model), and whether
it is approved (the last commit that changed it on the main branch came from a pull request merged by a person who
is not one of the declared system accounts).
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
FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n?", re.S)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def path_of(control_id: str, kind: str) -> str:
    return f"features/{control_id}/{kind}.md"


def links_path(control_id: str) -> str:
    return f"features/{control_id}/links.yaml"


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

    def approval(self, path: str) -> dict[str, Any]:
        """Whether `path` is approved on the main branch, and by which merge."""
        change: Change | None = self.client.last_change(path, self.branch)
        if change is None:
            return {"path": path, "published": False, "approved": False}
        approved = bool(
            change.pull_request and change.merged_by and change.merged_by.lower() not in self.system_accounts
        )
        found = {"path": path, "published": True, "approved": approved, "commit": change.commit}
        if change.pull_request:
            found |= {"pull_request": change.pull_request, "merged_by": change.merged_by, "url": change.url}
        else:
            found["reason"] = "the last change on the main branch did not come from a merged pull request"
        return found

    def require_approved(self, control_id: str, kind: str) -> dict[str, Any]:
        found = self.approval(path_of(control_id, kind))
        if not found["approved"]:
            raise ToolError(
                "not_approved",
                f"{kind}.md of {control_id} is not approved on your team's control repository: open its pull "
                "request with control_publish and have it merged first",
            )
        return found

    def read(self, path: str) -> str | None:
        try:
            return self.client.read_file(path, self.branch)
        except ConnectorError as exc:
            if exc.code == "not_found":
                return None
            raise

    def links(self, control_id: str) -> dict[str, Any]:
        text = self.read(links_path(control_id))
        doc = yaml.safe_load(text) if text else None
        return doc if isinstance(doc, dict) else {"writes": []}

    def record(self, control_id: str, entry: dict[str, Any]) -> None:
        """Adds one write and its results to the feature's links.yaml, committed directly on the main branch."""
        doc = self.links(control_id)
        doc.setdefault("writes", []).append({"at": _now(), "by": self.by, **entry})
        text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
        self.client.commit_file(links_path(control_id), text, self.branch, f"{control_id}: record {entry['action']}")


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


async def control_publish(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    """Opens a pull request on the team's control repository with a feature (and its stories) or a design, as the
    user. A design names a published feature (`control_id`) or brings the feature with it (`feature`)."""
    from user_agent_mcp.systems import _call

    control = Control(platform, caller)
    kind = args.get("kind")
    if kind not in KINDS:
        raise ToolError("invalid_argument", "kind must be feature or design")
    body = _body(args.get("content"))
    jira = [k for k in args.get("jira_keys") or [] if isinstance(k, str)][:50]
    control_id = args.get("control_id")
    files: dict[str, str] = {}
    meta = {"team": control.team, "drafted_by": control.by, "published": _now()}
    if control_id:
        if not isinstance(control_id, str) or not CONTROL_ID.match(control_id):
            raise ToolError("invalid_argument", "control_id looks like F-20261125-refunds")
    # Never a second pull request for the same artifact: an open one is returned instead.
    name_source = str(args.get("summary") or (args.get("feature") if kind == "design" else body) or body)
    slug = _slug(name_source.strip().splitlines()[0] if name_source.strip() else "feature")
    existing = _similar(await _call(lambda: _open_pull_requests(control)), kind, control_id, slug)
    if existing:
        return {
            "control_id": existing["control_id"],
            "kind": kind,
            "already_open": True,
            "pull_request": {"number": existing["number"], "url": existing["url"], "branch": existing["branch"]},
            "next": "a pull request for this is already open: have it merged (or closed) instead of opening another",
        }
    if kind == "feature":
        if not control_id:
            control_id = await _new_id(control, str(args.get("summary") or body.splitlines()[0]))
        files[path_of(control_id, "feature")] = _with_front_matter(
            body, {"control_id": control_id, "kind": "feature", **meta, **({"jira": jira} if jira else {})}
        )
    else:
        previous: dict[str, Any] = {}
        if control_id:
            feature = await _call(lambda: control.approval(path_of(control_id, "feature")))
            if not feature["published"]:
                raise ToolError("not_found", f"{control_id} has no published feature; bring it with `feature`")
            previous = {"path": feature["path"], "commit": feature["commit"], "approved": feature["approved"]}
        else:
            feature_body = _body(args.get("feature"))
            control_id = await _new_id(control, str(args.get("summary") or feature_body.splitlines()[0]))
            files[path_of(control_id, "feature")] = _with_front_matter(
                feature_body, {"control_id": control_id, "kind": "feature", **meta}
            )
            previous = {"path": path_of(control_id, "feature"), "in_this_pull_request": True}
        files[path_of(control_id, "design")] = _with_front_matter(
            body,
            {
                "control_id": control_id,
                "kind": "design",
                **meta,
                "previous": previous,
                **({"jira": jira} if jira else {}),
            },
        )
    keys = " ".join(jira[:5])
    title = str(args.get("title") or f"{control_id}: {kind}")[:200]
    if keys and keys not in title:
        title = f"{keys} {title}"[:200]
    description = str(args.get("description") or "")[:20_000]
    description += f"\n\n---\nPublished by {control.by} for team {control.team} ({control_id}, {kind}). Merging this "
    description += "pull request approves it (DEC-0012)."
    branch = f"sdlc/{control_id}/{kind}-{secrets.token_hex(3)}"
    changes = [FileChange(p, c) for p, c in files.items()]
    pr = await _call(
        lambda: control.client.open_pull_request(
            branch, control.branch, title, description.strip(), changes, f"{control_id}: {kind}"
        )
    )
    return {
        "control_id": control_id,
        "kind": kind,
        "pull_request": {"number": pr.number, "url": pr.url, "branch": pr.branch},
        "files": list(files),
        "next": "a person merges the pull request; then control_status shows the artifact as approved",
    }


async def _new_id(control: Control, summary: str) -> str:
    from user_agent_mcp.systems import _call

    base = f"F-{datetime.now(UTC):%Y%m%d}-{_slug(summary)}"
    for n in range(1, 20):
        candidate = base if n == 1 else f"{base[:46]}-{n}"
        found = await _call(lambda c=candidate: control.client.last_change(path_of(c, "feature"), control.branch))
        if found is None:
            return candidate
    raise ToolError("conflict", "too many features with this name today; give a different summary")


async def control_status(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    """Whether a feature's artifacts are approved on the team's control repository, what has been written from them,
    and, on request, their text. Finds the feature by control ID or by the Jira key of its feature issue."""
    from user_agent_mcp.systems import _call

    control = Control(platform, caller)
    control_id = args.get("control_id")
    jira_key = args.get("jira_key")
    if not control_id and isinstance(jira_key, str):
        control_id = await _control_id_of(platform, caller, jira_key)
    if not isinstance(control_id, str) or not CONTROL_ID.match(control_id):
        raise ToolError("invalid_argument", "give control_id (such as F-20261125-refunds) or a Jira feature key")
    artifacts = {}
    for kind in KINDS:
        found = await _call(lambda k=kind: control.approval(path_of(control_id, k)))
        if args.get("include_content") and found["published"]:
            text = await _call(lambda p=found["path"]: control.read(p))
            found["content"] = (text or "")[:MAX_ARTIFACT]
        artifacts[kind] = found
    links = await _call(lambda: control.links(control_id))
    result = {
        "control_id": control_id,
        "team": control.team,
        "repository": control.settings["repo"],
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
