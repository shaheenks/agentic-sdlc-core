"""`sdlc.audit` events beyond tool calls: tools_list and auth_failure (rejected tokens)."""

import json

import httpx
import pytest
from fastmcp import Client
from fastmcp.server.auth.providers.jwt import RSAKeyPair

from tests.support.entra import G_ENG_ALL, G_PAYMENTS_DEVS

MCP_HEADERS = {"Accept": "application/json, text/event-stream"}
BODY = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}


def audit_events(caplog, event: str) -> list[dict]:
    records = [json.loads(r.getMessage()) for r in caplog.records if r.name == "sdlc.audit"]
    return [r for r in records if r["event"] == event]


async def test_tools_list_is_audited(base_url, entra, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    token = entra.token(
        oid="aaaaaaaa-0000-0000-0000-00000000000a", groups=[G_ENG_ALL, G_PAYMENTS_DEVS]
    )
    async with Client(f"{base_url}/mcp", auth=token) as c:
        await c.list_tools()
    [record] = audit_events(caplog, "tools_list")
    assert record["oid"] == "aaaaaaaa-0000-0000-0000-00000000000a"
    assert record["teams"] == ["payments"] and "developer" in record["roles"]
    assert "review_code" in record["visible"] and "config_info" not in record["visible"]
    assert record["hidden_count"] >= 3  # approve_design, config_info, config_explain
    assert record["outcome"] == "ok" and record["config_version"].startswith("local-")


def post(base_url, authorization: str | None) -> httpx.Response:
    headers = dict(MCP_HEADERS)
    if authorization is not None:
        headers["Authorization"] = authorization
    return httpx.post(f"{base_url}/mcp", headers=headers, json=BODY)


@pytest.mark.parametrize(
    ("make_header", "reason"),
    [
        (lambda e: None, "missing_token"),
        (lambda e: "Basic dXNlcjpwYXNz", "malformed_token"),
        (lambda e: "Bearer not-a-jwt", "malformed_token"),
        (lambda e: f"Bearer {e.token(expires_in=-60)}", "expired"),
        (lambda e: f"Bearer {e.token(tid='99999999-9999-9999-9999-999999999999')}", "wrong_tenant"),
        (lambda e: f"Bearer {e.token(audience='api://someone-else')}", "wrong_audience"),
        (lambda e: f"Bearer {e.token(scp='User.Read')}", "missing_scope"),
        (lambda e: f"Bearer {e.token(key=RSAKeyPair.generate())}", "invalid_token"),  # forged
    ],
)
def test_rejected_tokens_are_audited(base_url, entra, caplog, make_header, reason):
    caplog.set_level("INFO", logger="sdlc.audit")
    header = make_header(entra)
    assert post(base_url, header).status_code == 401
    [record] = audit_events(caplog, "auth_failure")
    assert record["reason"] == reason
    assert record["status"] == 401 and record["path"].startswith("/mcp")
    if reason in ("expired", "wrong_tenant", "wrong_audience", "missing_scope", "invalid_token"):
        assert record["token_fingerprint"].startswith("sha256:")
        assert record["claimed"]["oid"]  # unverified claims, reported for investigation
    # the raw token never appears in the audit log
    raw = header.split(" ", 1)[1] if header and " " in header else None
    if raw and len(raw) > 20:
        assert raw not in json.dumps(record)


def test_forwarded_client_ip_is_recorded(base_url, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    httpx.post(
        f"{base_url}/mcp", json=BODY, headers={**MCP_HEADERS, "CF-Connecting-IP": "203.0.113.7"}
    )
    [record] = audit_events(caplog, "auth_failure")
    assert record["client_ip"] == "203.0.113.7"


def test_public_endpoints_are_not_audited_as_failures(base_url, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    assert httpx.get(f"{base_url}/healthz").status_code == 200
    assert httpx.get(f"{base_url}/.well-known/oauth-protected-resource/mcp").status_code == 200
    assert audit_events(caplog, "auth_failure") == []


async def test_successful_calls_produce_no_auth_failure(base_url, entra, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    async with Client(f"{base_url}/mcp", auth=entra.token()) as c:
        await c.call_tool("whoami", {})
    assert audit_events(caplog, "auth_failure") == []
    assert len(audit_events(caplog, "tool_call")) == 1
