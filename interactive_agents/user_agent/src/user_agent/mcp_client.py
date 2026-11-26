"""Deterministic workflow steps call user_agent_mcp tools directly, as the session's user (DEC-0010): the same
headers the agent's toolset sends, one stateless MCP `tools/call` per step (sdlc_adk.McpCaller). user_agent_mcp
decides what is allowed; a refusal comes back as a `StepError` with its code."""

import httpx
from sdlc_adk import PROTOCOL, StepError
from sdlc_adk import McpCaller as _McpCaller

from user_agent.identity import IdTokens, mcp_headers

__all__ = ["PROTOCOL", "McpCaller", "StepError"]


class McpCaller(_McpCaller):
    def __init__(
        self, url: str, tokens: IdTokens | None, timeout: float = 30.0, client: httpx.AsyncClient | None = None
    ):
        def headers(ctx) -> dict[str, str]:
            return mcp_headers(ctx.session.user_id, ctx.state, tokens)

        super().__init__(url, headers, timeout, client, "user_agent-workflow")
        self.tokens = tokens
