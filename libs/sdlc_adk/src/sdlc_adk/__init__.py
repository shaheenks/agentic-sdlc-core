"""What the platform's ADK agents share (user_agent, ci_workflow_agent): the runtime's Google ID token for an MCP
server, Gemini with retries, the skills of `skills/`, and a direct MCP `tools/call` for deterministic workflow steps.

Nothing here decides access: the headers a caller sends are its own, and the MCP server decides."""

import json
import os
import threading
import time
from collections.abc import Callable, Iterable
from functools import cache
from pathlib import Path
from typing import Any

import httpx

TOKEN_LIFETIME = 45 * 60  # Google ID tokens last an hour; refresh well before
PROTOCOL = "2026-07-28"
# Vertex AI answers 429 or 503 when a model is briefly over capacity; a workflow makes many calls, so one such answer
# must not fail the run. Retried with exponential backoff, up to about a minute.
RETRY_STATUS = [408, 429, 500, 502, 503, 504]


class IdTokens:
    """This runtime's Google ID token for one audience, from the metadata server, cached."""

    def __init__(self, audience: str, fetch: Callable[[str], str] | None = None) -> None:
        self.audience = audience
        self._fetch = fetch or fetch_id_token
        self._lock = threading.Lock()
        self._token: tuple[str, float] | None = None

    def get(self) -> str:
        with self._lock:
            if self._token is None or self._token[1] <= time.time():
                self._token = (self._fetch(self.audience), time.time() + TOKEN_LIFETIME)
            return self._token[0]


def fetch_id_token(audience: str) -> str:
    import google.auth.transport.requests
    import google.oauth2.id_token

    return google.oauth2.id_token.fetch_id_token(google.auth.transport.requests.Request(), audience)


def gemini(name: str, location: str, project: str | None = None):
    """An ADK Gemini model on Vertex AI in `location`, retrying the model's transient refusals."""
    from google.adk.models.google_llm import Gemini
    from google.genai import Client, types

    client = Client(
        vertexai=True,
        project=project or os.environ.get("GOOGLE_CLOUD_PROJECT"),
        location=location,
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                attempts=6, initial_delay=2.0, max_delay=30.0, exp_base=2.0, jitter=1.0, http_status_codes=RETRY_STATUS
            )
        ),
    )
    return Gemini(model=name, client=client)


def skills_dir(candidates: Iterable[str | Path | None]) -> Path:
    """The first existing folder of skills."""
    for candidate in candidates:
        if candidate and Path(candidate).is_dir():
            return Path(candidate)
    raise FileNotFoundError("no skills directory: set SDLC_SKILLS_DIR")


@cache
def load_skills(folder: Path) -> dict[str, str]:
    """Skill name -> its instructions (the SKILL.md body), with ADK's own loader."""
    from google.adk.skills import load_skills_from_dir

    return {s.frontmatter.name: s.instructions for s in load_skills_from_dir(folder)}


class StepError(Exception):
    """A tool call the MCP server refused or failed, with its code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


class McpCaller:
    """One stateless MCP `tools/call` per deterministic workflow step, with the headers `headers(ctx)` gives for the
    step's session. The server decides what is allowed; a refusal comes back as a StepError with its code."""

    def __init__(
        self,
        url: str,
        headers: Callable[[Any], dict[str, str]],
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
        client_name: str = "sdlc-workflow",
    ) -> None:
        self.url, self.headers, self.timeout, self.client, self.client_name = url, headers, timeout, client, client_name

    async def call(self, ctx: Any, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = self.headers(ctx) | {
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
                "io.modelcontextprotocol/clientInfo": {"name": self.client_name, "version": "1"},
                "io.modelcontextprotocol/clientCapabilities": {},
            },
        }
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params}
        client = self.client or httpx.AsyncClient(timeout=self.timeout)
        try:
            response = await client.post(self.url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise StepError("unavailable", "the MCP server did not answer") from exc
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
