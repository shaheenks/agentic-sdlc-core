"""The MCP server for calls made as a user (DEC-0002, DEC-0005).

Every request to /mcp or /api carries the user's Google account token. The server verifies it, resolves the
user's effective policy from the active configuration bundle, lists and allows only the tools that the
user and the calling surface may use, and audits every list and call without argument values. Artifacts
and connection secrets live under the user's own prefix of the mounted artifact bucket (DEC-0006).
"""

from sdlc_config_store import ConfigStore, source_from_url
from sdlc_directory import Directory
from sdlc_identity import GoogleTokens
from sdlc_policy import RateLimiter
from starlette.applications import Starlette

from user_agent_mcp.artifacts import ArtifactStore
from user_agent_mcp.connections import Cipher, ConnectionStore
from user_agent_mcp.http import build_app
from user_agent_mcp.platform import Platform
from user_agent_mcp.settings import Settings

SERVICE = "user_agent_mcp"
DEFAULT_PORT = 8080


def create_platform(settings: Settings, **overrides) -> Platform:
    """The service's parts, built from settings; tests replace some of them."""
    cipher = Cipher(settings.encryption_key, settings.encryption_key_version) if settings.encryption_key else None
    parts = {
        "store": ConfigStore(source_from_url(settings.config_source), settings.env, settings.config_refresh_seconds),
        "tokens": GoogleTokens(),
        "directory": Directory(),
        "limiter": RateLimiter(),
        "artifacts": ArtifactStore(settings.store_root),
        "connections": ConnectionStore(settings.store_root, cipher),
        **overrides,
    }
    return Platform(settings, **parts)


def create_app(settings: Settings | None = None, platform: Platform | None = None) -> Starlette:
    """The ASGI app. Without a platform it loads the active configuration first, and refuses to start when
    no verified bundle can be loaded (FR-CFG-001)."""
    if platform is None:
        platform = create_platform(settings or Settings.from_env())
        platform.store.load()
    return build_app(platform, SERVICE)
