"""The tools user_agent_mcp serves. Which of them a caller sees and may call is decided by the Access Policy
from the active configuration; nothing here names a role, team or tool group (FR-AUTHZ-001)."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

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
        "providers": {pid: {"name": p["name"], "edition": p["edition"]} for pid, p in sorted(providers.items())},
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
    provider, config = _provider(platform, caller, args)
    return platform.connections.save(
        caller.identity.user_id,
        provider,
        config,
        args.get("secret"),
        _str(args, "account", required=False),
        _str(args, "base_url", required=False),
    )


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
    )
}
