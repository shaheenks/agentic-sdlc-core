"""Who ci_workflow_agent calls event_agent_mcp as (FR-IDN-004, DEC-0015).

The run is the session: the event gateway creates it with the team, subscription, run ID, event and inputs in its
state, and nothing else writes them. Every call to event_agent_mcp carries them as headers, with the runtime's own
service account's Google ID token as proof (the system identity). A session without them is sent without them, and
event_agent_mcp refuses it (fail closed)."""

import os
from collections.abc import Callable, Mapping
from typing import Any

from sdlc_adk import IdTokens

SYSTEM_USER = "system"
SURFACE = "event_agents"
TEAM, SUBSCRIPTION, RUN, EVENT, INPUTS, WORKFLOW = (
    "sdlc_team",
    "sdlc_subscription",
    "sdlc_run_id",
    "sdlc_event",
    "sdlc_inputs",
    "sdlc_workflow",
)
STATE_KEYS = (TEAM, SUBSCRIPTION, RUN, EVENT, INPUTS, WORKFLOW)
EVENT_HEADERS = {
    "event_source": "X-SDLC-Event-Source",
    "event_type": "X-SDLC-Event-Type",
    "delivery_id": "X-SDLC-Event-Delivery",
    "subject": "X-SDLC-Event-Subject",
}


def mcp_headers(state: Mapping[str, Any], tokens: IdTokens | None) -> dict[str, str]:
    """The headers of one call to event_agent_mcp; none at all without a run."""
    run = {name: state.get(key) for name, key in (("team", TEAM), ("sub", SUBSCRIPTION), ("run", RUN))}
    if not all(isinstance(v, str) and v for v in run.values()):
        return {}
    headers = {"X-SDLC-Team": run["team"], "X-SDLC-Subscription": run["sub"], "X-SDLC-Run-Id": run["run"]}
    event = state.get(EVENT) or {}
    headers |= {h: str(event[k]) for k, h in EVENT_HEADERS.items() if isinstance(event, dict) and event.get(k)}
    if tokens is not None:
        headers["Authorization"] = f"Bearer {tokens.get()}"
    else:
        headers["X-SDLC-Surface"] = SURFACE  # local only: event_agent_mcp accepts it in mode trusted_header
    return headers


def header_provider(tokens: IdTokens | None) -> Callable[[Any], dict[str, str]]:
    def provide(ctx) -> dict[str, str]:
        return mcp_headers(ctx.state, tokens)

    return provide


def tokens_from_env(mcp_url: str, environ: Mapping[str, str] | None = None) -> IdTokens | None:
    """`SDLC_CALLER_AUTH=id_token` (default) proves the runtime with its ID token; `none` only against a local
    event_agent_mcp."""
    e = os.environ if environ is None else environ
    auth = e.get("SDLC_CALLER_AUTH", "id_token")
    if auth == "none":
        return None
    if auth != "id_token":
        raise ValueError("SDLC_CALLER_AUTH must be id_token or none")
    return IdTokens(e.get("SDLC_MCP_AUDIENCE") or mcp_url.removesuffix("/mcp"))
