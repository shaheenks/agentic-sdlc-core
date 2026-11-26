import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from sdlc_adk import IdTokens, McpCaller, StepError, skills_dir


def test_id_tokens_are_fetched_once_and_cached():
    calls = []
    tokens = IdTokens("https://mcp.example.test", fetch=lambda aud: calls.append(aud) or f"token-for-{aud}")
    assert tokens.get() == tokens.get() == "token-for-https://mcp.example.test"
    assert calls == ["https://mcp.example.test"]


def test_the_caller_sends_the_steps_headers_and_maps_refusals():
    seen = []

    def server(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        name = json.loads(request.content)["params"]["name"]
        if name == "denied":
            return httpx.Response(403, json={"error": "forbidden", "error_description": "not_a_system_team"})
        if name == "refused":
            text = json.dumps({"error": "not_approved", "message": "design.md is not approved"})
            return httpx.Response(
                200, json={"jsonrpc": "2.0", "id": 1, "result": {"content": [{"text": text}], "isError": True}}
            )
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text='data: {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"text": "{\\"ok\\": true}"}]}}\n',
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(server))
    caller = McpCaller("https://mcp/mcp", lambda ctx: {"X-SDLC-Team": ctx.state["team"]}, client=client)
    ctx = SimpleNamespace(state={"team": "payments"})
    assert asyncio.run(caller.call(ctx, "feature_status", {"control_id": "F-1"})) == {"ok": True}
    assert seen[0].headers["x-sdlc-team"] == "payments" and seen[0].headers["mcp-name"] == "feature_status"
    for name, code in (("denied", "forbidden"), ("refused", "not_approved")):
        with pytest.raises(StepError) as exc:
            asyncio.run(caller.call(ctx, name))
        assert exc.value.code == code


def test_the_first_existing_skills_folder_is_used(tmp_path):
    assert skills_dir([None, tmp_path / "missing", tmp_path]) == tmp_path
    with pytest.raises(FileNotFoundError):
        skills_dir([None, tmp_path / "missing"])
