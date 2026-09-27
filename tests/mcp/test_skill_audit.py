"""skill_access / skills_list audit events and error details for debugging."""

import json

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.support.entra import G_ENG_ALL, G_PAYMENTS_DEVS, G_PLATFORM_DEVS


def events(caplog, event: str) -> list[dict]:
    records = [json.loads(r.getMessage()) for r in caplog.records if r.name == "sdlc.audit"]
    return [r for r in records if r["event"] == event]


def client(base_url, entra, groups):
    return Client(f"{base_url}/mcp", auth=entra.token(groups=groups))


async def test_allowed_skill_access_is_recorded_with_rule(base_url, entra, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    async with client(base_url, entra, [G_ENG_ALL, G_PAYMENTS_DEVS]) as c:
        await c.call_tool("load_skill", {"name": "pci-checklist"})
    [access] = events(caplog, "skill_access")
    [call] = events(caplog, "tool_call")
    assert access["decision"] == "allow" and access["skill"] == "pci-checklist"
    assert access["matched_rule"] == "team:payments <- teams/payments.yaml#membership[0]"
    assert access["teams"] == ["payments"]
    assert access["request_id"] == call["request_id"] and len(call["request_id"]) == 16


@pytest.mark.parametrize(
    ("groups", "skill", "rule", "reason"),
    [
        (
            [G_ENG_ALL, G_PLATFORM_DEVS],
            "pci-checklist",
            "teams/payments.yaml#addons/skills/pci-checklist",
            "team add-on of 'payments'; caller is not a member",
        ),
        (
            [G_ENG_ALL, G_PAYMENTS_DEVS],
            "ledger-design-review",
            "teams/payments.yaml#addons/skills/ledger-design-review/access",
            "access requires roles ['lead']",
        ),
        (
            [G_ENG_ALL, G_PAYMENTS_DEVS],
            "design-review",
            "skills.yaml#skills/design-review/access",
            "access requires roles ['lead']",
        ),
        (
            [G_ENG_ALL],
            "test-case-gen",
            "default-deny",
            "no role of the caller grants 'test-case-gen', 'tag:engineering', '*'",
        ),
        ([G_ENG_ALL], "no-such-skill", "not-found", "no skill named 'no-such-skill' in config"),
    ],
)
async def test_denied_skill_access_records_the_real_reason(
    base_url, entra, caplog, groups, skill, rule, reason
):
    caplog.set_level("INFO", logger="sdlc.audit")
    async with client(base_url, entra, groups) as c:
        # the caller only learns "unknown skill", whatever the reason
        with pytest.raises(ToolError, match=f"^unknown skill '{skill}'$"):
            await c.call_tool("load_skill", {"name": skill})
    [access] = events(caplog, "skill_access")
    [call] = events(caplog, "tool_call")
    assert (access["decision"], access["matched_rule"], access["reason"]) == ("deny", rule, reason)
    # the tool call itself was permitted; the skill was not
    assert (call["decision"], call["outcome"], call["error_type"]) == (
        "allow",
        "tool_error",
        "ToolError",
    )
    assert call["error"] == f"unknown skill '{skill}'"
    assert call["request_id"] == access["request_id"]


async def test_skills_list_is_recorded(base_url, entra, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    async with client(base_url, entra, [G_ENG_ALL, G_PLATFORM_DEVS]) as c:
        await c.call_tool("list_skills", {})
    [listing] = events(caplog, "skills_list")
    assert listing["visible"] == ["infra-change-review", "test-case-gen", "write-user-story"]
    assert listing["hidden_count"] == 3
    assert "pci-checklist" not in json.dumps(listing)  # hidden names are not disclosed


async def test_unexpected_error_details_and_traceback(base_url, entra, caplog, monkeypatch):
    import sdlc_mcp_bootstrap.sdlc_tools as sdlc_tools

    def broken(tool, **inputs):
        raise RuntimeError("backend exploded: connection reset by peer")

    monkeypatch.setattr(sdlc_tools, "_stub", broken)
    caplog.set_level("INFO", logger="sdlc.audit")
    caplog.set_level("INFO", logger="sdlc.mcp")  # same level: set_level also sets the handler level
    async with client(base_url, entra, [G_ENG_ALL, G_PAYMENTS_DEVS]) as c:
        with pytest.raises(ToolError):
            await c.call_tool("review_code", {"repo": "payments-api"})
    [call] = events(caplog, "tool_call")
    assert call["outcome"] == "error"
    assert call["error_type"] == "builtins.RuntimeError"
    assert call["error"] == "backend exploded: connection reset by peer"
    [trace] = [r for r in caplog.records if r.name == "sdlc.mcp"]
    assert f"request_id={call['request_id']}" in trace.getMessage()
    assert trace.exc_info and trace.exc_info[0] is RuntimeError  # full traceback logged


async def test_long_error_text_is_kept_up_to_limit(base_url, entra, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    long_name = "x" * 600
    async with client(base_url, entra, [G_ENG_ALL]) as c:
        with pytest.raises(ToolError):
            await c.call_tool("load_skill", {"name": long_name})
    [call] = events(caplog, "tool_call")
    assert len(call["error"]) == 500
