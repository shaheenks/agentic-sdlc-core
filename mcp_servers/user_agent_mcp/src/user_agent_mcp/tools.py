"""The tools user_agent_mcp serves. Which of them a caller sees and may call is decided by the Access Policy
from the active configuration; nothing here names a role, team or tool group (FR-AUTHZ-001)."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from user_agent_mcp import control, systems
from user_agent_mcp.errors import ToolError

if TYPE_CHECKING:
    from user_agent_mcp.platform import Caller, Platform

Handler = Callable[["Platform", "Caller", dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Handler
    write: bool = False
    http_only: bool = False  # served on the HTTP API only, never listed or callable over MCP


def _schema(properties: dict[str, Any] | None = None, required: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"type": "object", "properties": properties or {}, "required": list(required), "additionalProperties": False}


NAME = {"type": "string", "description": "The artifact's name: letters, digits, '.', '_' or '-'."}
PROVIDER = {"type": "string", "description": "A connection provider declared in configuration, for example github."}


def _str(args: dict[str, Any], key: str, required: bool = True) -> str | None:
    value = args.get(key)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value:
        raise ToolError("invalid_argument", f"{key} must be a non-empty string")
    return value


def _provider(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> tuple[str, dict]:
    provider = _str(args, "provider")
    providers = caller.bundle.config.get("providers") or {}
    if provider not in providers:
        raise ToolError("unknown_provider", f"unknown provider; one of {', '.join(sorted(providers))}")
    return provider, providers[provider]


# Identity ------------------------------------------------------------------------------------------------


async def whoami(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    who = caller.identity
    return {
        "user_id": who.user_id,
        "email": who.email,
        "domain": who.domain,
        **caller.memberships.describe(),
        "access": caller.policy.describe(),
    }


# Knowledge (DEC-0011) ------------------------------------------------------------------------------------

MODES = ("hybrid", "vector", "keyword")


def _scope(caller: "Caller") -> dict[str, Any]:
    """The filter attribute: the sources the effective policy lets this user read here. No argument widens it."""
    return {"sources": sorted(caller.policy.sources)}


def _int_arg(args: dict[str, Any], key: str, default: int, low: int, high: int) -> int:
    value = args.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ToolError("invalid_argument", f"{key} must be an integer from {low} to {high}")
    return value


async def _knowledge(platform: "Platform", path: str, body: dict[str, Any]) -> dict[str, Any]:
    if platform.knowledge is None:
        raise ToolError("knowledge_unavailable", "knowledge search is not configured here")
    return await platform.knowledge.post(path, body)


async def knowledge_search(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    query = _str(args, "query")
    mode = args.get("mode", "hybrid")
    if mode not in MODES:
        raise ToolError("invalid_argument", f"mode must be one of {', '.join(MODES)}")
    scope = _scope(caller)
    found = await _knowledge(
        platform,
        "/search",
        {"query": query, "mode": mode, "limit": _int_arg(args, "limit", 8, 1, 20), "filter": scope},
    )
    return {"team": caller.policy.team, "sources": scope["sources"], "results": found.get("results", [])}


async def knowledge_graph(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    entity, name = _str(args, "entity", required=False), _str(args, "name", required=False)
    if not entity and not name:
        raise ToolError("invalid_argument", "give a name or an entity ID")
    body = {"depth": _int_arg(args, "depth", 1, 1, 2), "filter": _scope(caller)}
    body |= {"entity": entity} if entity else {"name": name}
    found = await _knowledge(platform, "/graph", body)
    return {"team": caller.policy.team, **{k: found.get(k, []) for k in ("seeds", "nodes", "edges")}}


# Artifacts -----------------------------------------------------------------------------------------------


async def artifact_list(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    return {"artifacts": platform.artifacts.list(caller.identity.user_id)}


async def artifact_read(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    version = args.get("version")
    if version is not None and (not isinstance(version, int) or isinstance(version, bool) or version < 1):
        raise ToolError("invalid_argument", "version must be a positive integer")
    return platform.artifacts.read(caller.identity.user_id, _str(args, "name"), version)


async def artifact_save(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    limits = (caller.bundle.config.get("platform") or {}).get("artifacts") or {}
    content = args.get("content")
    if not isinstance(content, str):
        raise ToolError("invalid_argument", "content must be a string")
    return platform.artifacts.save(
        caller.identity.user_id,
        _str(args, "name"),
        content,
        _str(args, "content_type", required=False) or "text/markdown",
        allowed_types=list(limits.get("content_types") or []),
        max_bytes=int(limits.get("max_bytes") or 0),
        lineage={
            "run_id": _str(args, "run_id", required=False) or caller.run_id,
            "step": _str(args, "step", required=False) or caller.step,
            "workflow_version": _str(args, "workflow_version", required=False),
        },
        classification=_str(args, "classification", required=False) or "internal",
    )


async def artifact_delete(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    return platform.artifacts.delete(caller.identity.user_id, _str(args, "name"))


# Connections ---------------------------------------------------------------------------------------------


async def connection_list(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    providers = caller.bundle.config.get("providers") or {}
    return {
        "connections": platform.connections.list(caller.identity.user_id, providers),
        "providers": {
            pid: {"name": p["name"], "system": p["system"], "edition": p["edition"]}
            for pid, p in sorted(providers.items())
        },
    }


async def connection_start(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    provider, config = _provider(platform, caller, args)
    if not platform.settings.sdlc_ui_url:
        raise ToolError("unavailable", "no secure entry page is configured in this environment")
    return {
        "provider": provider,
        "name": config["name"],
        "entry_url": f"{platform.settings.sdlc_ui_url}/connections/{provider}",
        "instructions": "Open the link and enter the token there. Never paste a token into the conversation.",
    }


async def connection_save(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    """Signs in with the token first: a token the provider refuses is not stored. One that cannot be checked here
    (no site to test against, the server unreachable) is stored as untested."""
    from sdlc_connectors import Credential

    provider, config = _provider(platform, caller, args)
    secret, account = args.get("secret"), _str(args, "account", required=False)
    base_url = _str(args, "base_url", required=False)
    if not isinstance(secret, str) or not secret.strip() or len(secret) > 4096:
        raise ToolError("invalid_secret", "the secret must be 1-4096 characters")
    if config["edition"] == "data_center" and (not base_url or not base_url.startswith("https://")):
        raise ToolError("invalid_base_url", "a Data Center connection needs its server's https:// URL")
    if config["system"] == "jira" and config["edition"] == "cloud" and not account:
        raise ToolError("account_required", "a Jira Cloud token signs in with your Atlassian account email: give it")
    test_url = base_url if config["edition"] == "data_center" else config.get("base_url")
    checked = await systems.sign_in(caller, provider, Credential(secret, account), test_url)
    if checked["status"] == "refused":
        raise ToolError(
            "invalid_token", f"{config['name']} did not accept this token ({checked['reason']}); nothing was saved"
        )
    saved = platform.connections.save(caller.identity.user_id, provider, config, secret, account, base_url)
    return {**saved, **checked}


async def connection_revoke(platform: "Platform", caller: "Caller", args: dict[str, Any]) -> dict[str, Any]:
    provider, _ = _provider(platform, caller, args)
    return platform.connections.revoke(caller.identity.user_id, provider)


TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool("whoami", "Show who you are: your user ID, teams, user groups and what you may use.", _schema(), whoami),
        Tool("artifact_list", "List your own artifacts with their versions.", _schema(), artifact_list),
        Tool(
            "artifact_read",
            "Read one of your artifacts; the latest version unless a version is given.",
            _schema({"name": NAME, "version": {"type": "integer", "minimum": 1}}, ("name",)),
            artifact_read,
        ),
        Tool(
            "artifact_save",
            "Save an artifact, or a new version of it. Artifacts are deleted 7 days after they are written.",
            _schema(
                {
                    "name": NAME,
                    "content": {"type": "string"},
                    "content_type": {"type": "string", "description": "Default text/markdown."},
                    "run_id": {"type": "string"},
                    "step": {"type": "string"},
                    "workflow_version": {"type": "string"},
                    "classification": {"type": "string", "description": "Default internal."},
                },
                ("name", "content"),
            ),
            artifact_save,
            write=True,
        ),
        Tool(
            "artifact_delete",
            "Delete one of your artifacts with all its versions.",
            _schema({"name": NAME}, ("name",)),
            artifact_delete,
            write=True,
        ),
        Tool(
            "connection_list",
            "List your connections to downstream systems and the providers you can connect.",
            _schema(),
            connection_list,
        ),
        Tool(
            "connection_start",
            "Get the link to the secure page where you add or replace a connection's token. Tokens are never "
            "entered in the conversation.",
            _schema({"provider": PROVIDER}, ("provider",)),
            connection_start,
        ),
        Tool(
            "connection_revoke",
            "Remove one of your connections; it stops being used at once.",
            _schema({"provider": PROVIDER}, ("provider",)),
            connection_revoke,
            write=True,
        ),
        Tool(
            "connection_save",
            "Save a connection secret (secure entry page only).",
            _schema(
                {
                    "provider": PROVIDER,
                    "secret": {"type": "string"},
                    "account": {"type": "string"},
                    "base_url": {"type": "string"},
                },
                ("provider", "secret"),
            ),
            connection_save,
            write=True,
            http_only=True,
        ),
        Tool(
            "connection_test",
            "Check that one of your connections signs in, and as whom. The token is never shown.",
            _schema({"provider": PROVIDER}, ("provider",)),
            systems.connection_test,
        ),
        Tool(
            "team_systems",
            "The Jira projects, Confluence spaces, repositories (each list with its default) and control repository "
            "of your teams, or of this run's team.",
            _schema(),
            systems.team_systems,
        ),
        Tool(
            "jira_get_issue",
            "Read a Jira issue of your team's project with your own connection; a feature comes with its stories.",
            _schema({"key": {"type": "string", "description": "A Jira issue key, such as PAY-12."}}, ("key",)),
            systems.jira_get_issue,
        ),
        Tool(
            "jira_search",
            "Find issues in your team's Jira project by words, issue type or status.",
            _schema(
                {
                    "text": {"type": "string"},
                    "issue_type": {"type": "string", "description": "For example Feature or User Story."},
                    "status": {"type": "string", "description": "A status name, such as To Do."},
                }
            ),
            systems.jira_search,
        ),
        Tool(
            "jira_create_feature",
            "Create the feature and its user stories in one of the run's team's Jira projects, as you, from a "
            "feature.md approved on the team's control repository (control_publish, then a person merges). The keys "
            "are recorded there. Refused while the feature is not approved, and once it is already in Jira.",
            _schema(
                {
                    "control_id": {
                        "type": "string",
                        "description": "The published feature, such as F-20261125-refunds.",
                    },
                    "project": {
                        "type": "string",
                        "description": "A Jira project key of the run's team; its default project if left out.",
                    },
                    "feature": {
                        "type": "object",
                        "properties": {"summary": {"type": "string"}, "description": {"type": "string"}},
                        "required": ["summary"],
                    },
                    "stories": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"summary": {"type": "string"}, "description": {"type": "string"}},
                            "required": ["summary"],
                        },
                    },
                },
                ("control_id", "feature", "stories"),
            ),
            systems.jira_create_feature,
            write=True,
        ),
        Tool(
            "jira_link_design",
            "Link a design specification approved on the team's control repository to its Jira feature; recorded "
            "there.",
            _schema({"control_id": {"type": "string"}}, ("control_id",)),
            systems.jira_link_design,
            write=True,
        ),
        Tool(
            "control_publish",
            "Open a pull request on the run's team's control repository with a feature and its stories (kind "
            "feature) or a design specification (kind design), as you. A person merging it approves it; only then "
            "can it be written to Jira or handed to implementation. Use only when the user asks to add the work "
            "to Jira or hand it on; drafts otherwise stay the user's artifacts.",
            _schema(
                {
                    "kind": {"type": "string", "enum": ["feature", "design"]},
                    "content": {"type": "string", "description": "The artifact's Markdown, without front matter."},
                    "control_id": {
                        "type": "string",
                        "description": "For a design: the published feature it is for. Left out for a new feature.",
                    },
                    "feature": {
                        "type": "string",
                        "description": "For a design whose feature is not published yet: the feature's Markdown.",
                    },
                    "summary": {"type": "string", "description": "A few words naming the feature, for its ID."},
                    "jira_keys": {"type": "array", "items": {"type": "string"}},
                    "title": {"type": "string"},
                    "description": {
                        "type": "string",
                        "description": "The pull request text: the review findings and what the user decided.",
                    },
                },
                ("kind", "content"),
            ),
            control.control_publish,
            write=True,
        ),
        Tool(
            "control_status",
            "Whether a feature's artifacts (feature.md, design.md) are approved on the run's team's control "
            "repository, who merged them, what has been written from them, and on request their text. Give the "
            "control ID or the Jira key of a feature created from it.",
            _schema(
                {
                    "control_id": {"type": "string"},
                    "jira_key": {"type": "string"},
                    "include_content": {"type": "boolean"},
                }
            ),
            control.control_status,
        ),
        Tool(
            "repo_list",
            "List a folder of one of your team's repositories.",
            _schema(
                {
                    "repo": {
                        "type": "string",
                        "description": "owner/name of one of your team's repositories (team_systems).",
                    },
                    "path": {"type": "string"},
                    "ref": {"type": "string"},
                },
                ("repo",),
            ),
            systems.repo_list,
        ),
        Tool(
            "repo_read_file",
            "Read a file of one of your team's repositories.",
            _schema(
                {
                    "repo": {
                        "type": "string",
                        "description": "owner/name of one of your team's repositories (team_systems).",
                    },
                    "path": {"type": "string"},
                    "ref": {"type": "string"},
                },
                ("repo", "path"),
            ),
            systems.repo_read_file,
        ),
        Tool(
            "knowledge_search",
            "Search the knowledge sources you may read (in a team's run: that team's sources) by meaning, keyword "
            "or both. Each result has its source, a link to the original and the matching text.",
            _schema(
                {
                    "query": {"type": "string", "description": "What to look for, in words."},
                    "mode": {"type": "string", "enum": list(MODES), "description": "Default hybrid."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20, "description": "Default 8."},
                },
                ("query",),
            ),
            knowledge_search,
        ),
        Tool(
            "knowledge_graph",
            "Explore the knowledge graph around an entity, found by name or ID: files, sections, code symbols "
            "and concepts, and how they link, within the sources you may read.",
            _schema(
                {
                    "name": {"type": "string", "description": "Part of an entity's name, e.g. a concept or file."},
                    "entity": {"type": "string", "description": "An entity ID from an earlier answer."},
                    "depth": {"type": "integer", "minimum": 1, "maximum": 2, "description": "Default 1."},
                },
            ),
            knowledge_graph,
        ),
    )
}
