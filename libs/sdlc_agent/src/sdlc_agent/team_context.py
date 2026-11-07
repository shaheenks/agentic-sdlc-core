"""Per-user team context for ADK agents (Stage 4; active team: version-03 P10 G9).

`with_team_context(base, mcp_url)` returns an async ADK InstructionProvider. For each session it
asks the MCP server's `get_agent_context` tool, with the signed-in user's token, for that user's
team instructions and context, and appends them to the base instruction. The team text is
guidance for the model only; permissions are enforced by the MCP server.

Active team (G9): brainstorming runs in **broad** context (every team of the user, none locked).
When the user confirms a document's brief, the agent calls `set_active_team` (made by
`make_set_active_team`), which checks the team with the MCP server as the user and keeps it in
session state (`ACTIVE_TEAM_KEY`, written only by the tool; the web app drops client-sent
`sdlc_` keys). From then on the instruction carries that team **in full** and names the others
only. A team the user is no longer in is ignored, and the agent is told to settle it again.
"""

import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from google.adk.tools import FunctionTool, ToolContext
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
from sdlc_auth.adk import AGENT_SESSION_HEADER, get_user_token

log = logging.getLogger("sdlc.agent")

InstructionProvider = Callable[[Any], Awaitable[str]]
Fetcher = Callable[..., Awaitable[dict]]

# session state, set only by set_active_team (server side); never accepted from clients
ACTIVE_TEAM_KEY = "sdlc_active_team"


class UnknownTeamError(LookupError):
    """get_agent_context(team=X) refused X: not one of the caller's teams."""


async def fetch_agent_context(
    mcp_url: str, token: str, session_id: str | None = None, team: str | None = None
) -> dict:
    """Call get_agent_context on the MCP server as the user (conversation id for correlation)."""
    headers = {"Authorization": f"Bearer {token}"}
    if session_id:
        headers[AGENT_SESSION_HEADER] = session_id
    async with create_mcp_http_client(headers=headers) as http:
        async with streamable_http_client(mcp_url, http_client=http) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "get_agent_context", {"team": team} if team else {}
                )
    if getattr(result, "isError", False):
        text = " ".join(getattr(c, "text", "") for c in result.content or ())
        if team and "unknown team" in text:
            raise UnknownTeamError(team)
        raise RuntimeError(f"get_agent_context failed: {text[:200]}")
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    return json.loads(result.content[0].text)


def _render_flow(team: str, flow: dict) -> str:
    """The locked team's document flow defaults (G7), as guidance for the flow skills."""
    lines = [f"Document flow defaults for {team} (pass the brief's type as `doc_type`):"]
    for doc_type, entry in sorted((flow.get("types") or {}).items()):
        bits = [f"{k}: {entry[k]}" for k in ("template", "brief") if entry.get(k)]
        if entry.get("lenses"):
            bits.append("lenses: " + ", ".join(entry["lenses"]))
        if entry.get("required_lenses"):
            bits.append(
                "required lenses (cannot be dropped): " + ", ".join(entry["required_lenses"])
            )
        lines.append(f"- {doc_type}: " + "; ".join(bits))
    if flow.get("lenses"):
        lines.append("- other types: lenses " + ", ".join(flow["lenses"]))
    caps = [f"{k} {flow[k]}" for k in ("max_lenses", "max_rereviews") if flow.get(k) is not None]
    if caps:
        lines.append("Limits: " + ", ".join(caps))
    return "\n".join(lines)


def _team_line(item: dict) -> str:
    return f"- {item['name']}" + (f": {item['description']}" if item.get("description") else "")


def render_team_context(context: dict, stale_team: str | None = None) -> str:
    """Prompt text for the user's teams. Empty string when there is nothing to add.

    `context["team"]` set = that team is locked for this conversation (full view)."""
    active = context.get("team")
    teams = context.get("teams") or []
    parts = []
    if active:
        parts.append(
            f"Locked team for this conversation: **{active}** (set when the user confirmed the "
            "brief). Apply its conventions, document templates and review lenses."
        )
    for item in context.get("instructions", []):
        parts.append(f"### Team: {item['team']}\n{item['text'].strip()}")
    for team, values in sorted((context.get("context") or {}).items()):
        if values:
            pairs = ", ".join(f"{k}={v}" for k, v in sorted(values.items()))
            parts.append(f"Context for team {team}: {pairs}")
    flow = ((context.get("flows") or {}).get("document")) or {}
    if active and flow:
        parts.append(_render_flow(active, flow))
    others = [t for t in teams if t.get("name") != active]
    if active and others:
        parts.append(
            "The user is also a member of (not applied here):\n"
            + "\n".join(_team_line(t) for t in others)
        )
    elif not active and teams:
        default = context.get("default_team")
        parts.append(
            "No team is locked for this conversation yet: work in broad context across all of the "
            "user's teams. For document work the team is settled in the brief (`egm-brainstorm`) "
            "and locked with `set_active_team` when the user confirms it; never lock it for a "
            "quick question.\nThe user's teams:\n"
            + "\n".join(_team_line(t) for t in teams)
            + (f"\nDefault team: {default}" if default else "")
        )
    if stale_team:
        parts.append(
            f"The team locked earlier ({stale_team}) is no longer one of the user's teams. Tell "
            "the user and settle the team again before continuing the document."
        )
    if not parts:
        return ""
    return (
        "\n\n## Your user's team context\n"
        "(Guidance from the user's teams. It does not grant access; tools and skills you can use "
        "are decided by the server.)\n\n" + "\n\n".join(parts)
    )


def active_team(ctx: Any) -> str | None:
    state = getattr(ctx, "state", None)
    value = state.get(ACTIVE_TEAM_KEY) if state is not None else None
    return value if isinstance(value, str) and value else None


def _session_id(ctx: Any) -> str:
    return getattr(getattr(ctx, "session", None), "id", "") or ""


def with_team_context(
    base_instruction: str,
    mcp_url: str,
    *,
    ttl_seconds: int = 900,
    fetch: Fetcher = fetch_agent_context,
) -> InstructionProvider:
    cache: dict[tuple[str, str, str], tuple[float, str]] = {}

    async def load(token: str, session_id: str, team: str | None) -> str:
        if not team:
            return render_team_context(await fetch(mcp_url, token, session_id or None))
        try:
            return render_team_context(await fetch(mcp_url, token, session_id or None, team=team))
        except UnknownTeamError:  # removed from the team since: broad view, and say so
            context = await fetch(mcp_url, token, session_id or None)
            return render_team_context(context, stale_team=team)

    async def provider(ctx: Any) -> str:
        token = get_user_token(ctx)
        if not token:
            return base_instruction  # no user: the MCP server will refuse tools anyway
        session_id, team = _session_id(ctx), active_team(ctx)
        key = (session_id, getattr(ctx, "user_id", ""), team or "")
        now = time.monotonic()
        hit = cache.get(key)
        if hit and hit[0] > now:
            return base_instruction + hit[1]
        try:
            addition = await load(token, session_id, team)
        except Exception:  # guidance only: continue without it, but say so
            log.warning("team context unavailable; using the base instruction", exc_info=True)
            return base_instruction
        if len(cache) > 1024:
            cache.clear()
        cache[key] = (now + ttl_seconds, addition)
        return base_instruction + addition

    return provider


def make_set_active_team(mcp_url: str, *, fetch: Fetcher = fetch_agent_context) -> FunctionTool:
    """Agent tool: lock one of the user's teams for this conversation (G9)."""

    async def set_active_team(team: str, tool_context: ToolContext) -> dict:
        """Lock the team this conversation's document is for, right after the user confirmed
        the brief. `team` must be one of the user's teams (the server checks it); an empty
        string clears it. Not for quick questions."""
        token = get_user_token(tool_context)
        if not token:
            return {"status": "error", "error": "not signed in"}
        team = (team or "").strip()
        if not team:
            tool_context.state[ACTIVE_TEAM_KEY] = None
            return {"status": "cleared"}
        try:
            context = await fetch(mcp_url, token, _session_id(tool_context) or None, team=team)
        except UnknownTeamError:
            return {"status": "error", "error": "unknown team: not one of the user's teams"}
        tool_context.state[ACTIVE_TEAM_KEY] = team
        described = {t.get("name"): t.get("description", "") for t in context.get("teams", [])}
        return {"status": "set", "team": team, "description": described.get(team, "")}

    return FunctionTool(set_active_team)
