"""The MCP server for scheduled and event-triggered runs, as the system identity (DEC-0007, DEC-0015).

Every request to /mcp comes from the event agents' runtime: a declared caller of a surface marked `system: true`,
proved by its service account's Google ID token, forwarding no user. It names the run it acts in (the team, the
subscription that started it, the run ID and the event's metadata); the system identity's policy comes from
`system.yaml` of the active configuration, and a write tool is allowed only when the run's subscription declares it.
Downstream systems are reached with the machine users' system connections, whose tokens are environment variables
from Secret Manager. Every list and call is audited with the event's metadata and never argument values.
"""

from sdlc_config_store import ConfigStore, source_from_url
from sdlc_identity import GoogleTokens
from starlette.applications import Starlette

from event_agent_mcp.http import build_app
from event_agent_mcp.platform import Platform
from event_agent_mcp.settings import Settings
from event_agent_mcp.workspace import JobRunner, LocalRunner

SERVICE = "event_agent_mcp"
DEFAULT_PORT = 8081


def create_platform(settings: Settings, **overrides) -> Platform:
    """The service's parts, built from settings; tests replace some of them."""
    workspace = None
    if settings.workspace_mode == "job":
        workspace = JobRunner(settings.workspace_job, settings.workspace_timeout_seconds)
    elif settings.workspace_mode == "local":
        workspace = LocalRunner()
    parts = {
        "store": ConfigStore(source_from_url(settings.config_source), settings.env, settings.config_refresh_seconds),
        "tokens": GoogleTokens(),
        "workspace": workspace,
        **overrides,
    }
    return Platform(settings, **parts)


def create_app(settings: Settings | None = None, platform: Platform | None = None) -> Starlette:
    """The ASGI app. Without a platform it loads the active configuration first, and refuses to start when no
    verified bundle can be loaded (FR-CFG-001)."""
    if platform is None:
        platform = create_platform(settings or Settings.from_env())
        platform.store.load()
    return build_app(platform, SERVICE)
