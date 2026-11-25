"""Deterministic workflow steps call user_agent_mcp tools directly, as the session's user (DEC-0010): the same
headers the agent's toolset sends, one stateless MCP `tools/call` per step. user_agent_mcp decides what is allowed;
a refusal comes back as a `StepError` with its code."""

import json
from typing import Any

import httpx

from user_agent.identity import IdTokens, mcp_headers

PROTOCOL = "2026-07-28"


class StepError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


class McpCaller:
    def __init__(
        self, url: str, tokens: IdTokens | None, timeout: float = 30.0, client: httpx.AsyncClient | None = None
    ):
        self.url, self.tokens, self.timeout, self.client = url, tokens, timeout, client

    async def call(self, ctx: Any, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = mcp_headers(ctx.session.user_id, ctx.state, self.tokens)
        headers |= {
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL,
            "Mcp-Method": "tools/call",
            "Mcp-Name": name,
        }
        params = {
            "name": name,
            "arguments": arguments or {},
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": PROTOCOL,
                "io.modelcontextprotocol/clientInfo": {"name": "user_agent-workflow", "version": "1"},
                "io.modelcontextprotocol/clientCapabilities": {},
            },
        }
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params}
        client = self.client or httpx.AsyncClient(timeout=self.timeout)
        try:
            response = await client.post(self.url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise StepError("unavailable", "user_agent_mcp did not answer") from exc
        finally:
            if self.client is None:
                await client.aclose()
        if response.status_code >= 400:
            try:
                error = response.json()
            except ValueError:
                error = {}
            raise StepError(error.get("error", "refused"), error.get("error_description") or error.get("message", ""))
        message = _message(response)
        if "error" in message:
            raise StepError("protocol", str((message["error"] or {}).get("message", "MCP error")))
        result = message.get("result") or {}
        text = ((result.get("content") or [{}])[0]).get("text", "{}")
        data = json.loads(text) if text else {}
        if result.get("isError") or (isinstance(data, dict) and "error" in data and len(data) <= 3):
            raise StepError(str(data.get("error", "failed")), str(data.get("message", "")))
        return data


def _message(response: httpx.Response) -> dict[str, Any]:
    """A JSON-RPC message from a JSON body or the last `data:` line of an event stream."""
    if "text/event-stream" in response.headers.get("content-type", ""):
        lines = [line[5:].strip() for line in response.text.splitlines() if line.startswith("data:")]
        return json.loads(lines[-1]) if lines else {}
    return response.json()
