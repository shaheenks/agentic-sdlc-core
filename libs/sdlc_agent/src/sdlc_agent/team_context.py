"""Per-user team context for ADK agents (Stage 4).

`with_team_context(base, mcp_url)` returns an async ADK InstructionProvider. For each session it
asks the MCP server's `get_agent_context` tool, with the signed-in user's token, for that user's
team instructions and context, and appends them to the base instruction. The team text is
guidance for the model only; permissions are enforced by the MCP server.
"""

import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
from sdlc_auth.adk import AGENT_SESSION_HEADER, get_user_token

log = logging.getLogger("sdlc.agent")

InstructionProvider = Callable[[Any], Awaitable[str]]
Fetcher = Callable[..., Awaitable[dict]]


async def fetch_agent_context(mcp_url: str, token: str, session_id: str | None = None) -> dict:
    """Call get_agent_context on the MCP server as the user (conversation id for correlation)."""
    headers = {"Authorization": f"Bearer {token}"}
    if session_id:
        headers[AGENT_SESSION_HEADER] = session_id
    async with create_mcp_http_client(headers=headers) as http:
        async with streamable_http_client(mcp_url, http_client=http) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("get_agent_context", {})
    if getattr(result, "isError", False):
        raise RuntimeError(f"get_agent_context failed: {result}")
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    return json.loads(result.content[0].text)


def render_team_context(context: dict) -> str:
    """Prompt text for the user's teams. Empty string when there is nothing to add."""
    parts = []
    for item in context.get("instructions", []):
        parts.append(f"### Team: {item['team']}\n{item['text'].strip()}")
    for team, values in sorted((context.get("context") or {}).items()):
        if values:
            pairs = ", ".join(f"{k}={v}" for k, v in sorted(values.items()))
            parts.append(f"Context for team {team}: {pairs}")
    if not parts:
        return ""
    return (
        "\n\n## Your user's team context\n"
        "(Guidance from the user's teams. It does not grant access; tools and skills you can use "
        "are decided by the server.)\n\n" + "\n\n".join(parts)
    )


def with_team_context(
    base_instruction: str,
    mcp_url: str,
    *,
    ttl_seconds: int = 900,
    fetch: Fetcher = fetch_agent_context,
) -> InstructionProvider:
    cache: dict[tuple[str, str], tuple[float, str]] = {}

    async def provider(ctx: Any) -> str:
        token = get_user_token(ctx)
        if not token:
            return base_instruction  # no user: the MCP server will refuse tools anyway
        session_id = getattr(getattr(ctx, "session", None), "id", "") or ""
        key = (session_id, getattr(ctx, "user_id", ""))
        now = time.monotonic()
        hit = cache.get(key)
        if hit and hit[0] > now:
            return base_instruction + hit[1]
        try:
            addition = render_team_context(await fetch(mcp_url, token, session_id or None))
        except Exception:  # guidance only: continue without it, but say so
            log.warning("team context unavailable; using the base instruction", exc_info=True)
            return base_instruction
        if len(cache) > 1024:
            cache.clear()
        cache[key] = (now + ttl_seconds, addition)
        return base_instruction + addition

    return provider
