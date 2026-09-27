"""Stage 3c/3e: RBAC enforced by the MCP server over real HTTP (tools/list + tools/call)."""

import json

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from sdlc_config import ConfigStore, load_snapshot
from sdlc_mcp_bootstrap.server import build_server

from tests.support.entra import (
    G_ENG_ALL,
    G_PAYMENTS_DEVS,
    G_PLATFORM_DEVS,
    TEST_ENV,
)

G_PAYMENTS_LEADS = "00000000-0000-0000-0000-000000000003"
G_PLATFORM_ADMINS = "00000000-0000-0000-0000-000000000005"

PERSONAS = {
    "nobody": [],
    "viewer": [G_ENG_ALL],
    "payments_dev": [G_ENG_ALL, G_PAYMENTS_DEVS],
    "payments_lead": [G_ENG_ALL, G_PAYMENTS_LEADS],
    "platform_dev": [G_ENG_ALL, G_PLATFORM_DEVS],
    "admin": [G_ENG_ALL, G_PLATFORM_ADMINS],
}
BASICS = {"ping", "whoami"}
VIEWER = BASICS | {"list_skills", "load_skill", "get_agent_context"}  # registered viewer tools
DEVELOPER = VIEWER | {"review_code", "generate_tests"}


def client(base_url: str, token: str) -> Client:
    return Client(f"{base_url}/mcp", auth=token)


async def tools_for(base_url, entra, persona) -> set[str]:
    async with client(base_url, entra.token(groups=PERSONAS[persona])) as c:
        return {t.name for t in await c.list_tools()}


@pytest.mark.parametrize(
    ("persona", "expected"),
    [
        ("nobody", BASICS),
        ("viewer", VIEWER),
        ("payments_dev", DEVELOPER),
        ("payments_lead", DEVELOPER | {"approve_design"}),
        ("platform_dev", DEVELOPER),
        ("admin", DEVELOPER | {"approve_design", "config_info", "config_explain"}),
    ],
)
async def test_tools_list_is_filtered_per_persona(base_url, entra, persona, expected):
    assert await tools_for(base_url, entra, persona) == expected


async def test_payments_dev_calls_within_limits_only(base_url, entra):
    async with client(base_url, entra.token(groups=PERSONAS["payments_dev"])) as c:
        ok = (await c.call_tool("review_code", {"repo": "payments-api"})).data
        assert ok["stub"] is True and ok["inputs"]["repo"] == "payments-api"
        with pytest.raises(ToolError, match="repo='platform-infra' is not allowed"):
            await c.call_tool("review_code", {"repo": "platform-infra"})
        # Hidden tools cannot be called either
        with pytest.raises(ToolError, match="not granted"):
            await c.call_tool("approve_design", {"repo": "payments-api", "design_id": "d1"})
        with pytest.raises(ToolError, match="not granted"):
            await c.call_tool("config_info", {})


async def test_platform_dev_gets_platform_repos(base_url, entra):
    async with client(base_url, entra.token(groups=PERSONAS["platform_dev"])) as c:
        assert (await c.call_tool("generate_tests", {"repo": "platform-ci", "target": "x"})).data
        with pytest.raises(ToolError, match="not allowed"):
            await c.call_tool("generate_tests", {"repo": "payments-api", "target": "x"})


async def test_admin_tools(base_url, entra, store):
    async with client(base_url, entra.token(groups=PERSONAS["admin"])) as c:
        info = (await c.call_tool("config_info", {})).data
        assert info["config_version"] == store.current().version
        assert info["counts"]["teams"] >= 2
        explained = (
            await c.call_tool("config_explain", {"groups": ["eng-all", "payments-devs", "ghosts"]})
        ).data
        assert explained["tools"]["review_code"]["constraints"] == {
            "repo": ["payments-api", "payments-ui"]
        }
        assert explained["unknown_groups"] == ["ghosts"]
        # admin is unconstrained
        assert (await c.call_tool("review_code", {"repo": "any-repo"})).data["stub"]


async def test_whoami_explain_shows_own_policy(base_url, entra):
    token = entra.token(groups=[*PERSONAS["payments_dev"], "Payments-Admins-OnPrem"])
    async with client(base_url, token) as c:
        me = (await c.call_tool("whoami", {"explain": True})).data
    assert me["groups"] == ["eng-all", "payments-devs"]
    assert me["non_guid_group_claims"] == 1  # E10: on-prem style group name flagged
    assert set(me["policy"]["teams"]) == {"payments"}
    assert me["policy"]["tools"]["review_code"]["constraint_sources"] == [
        "teams/payments.yaml#policy/tools/constraints/review_code"
    ]


async def test_app_roles_are_reported(base_url, entra):
    token = entra.token(groups=[G_ENG_ALL], roles=["SDLC.Reader"])
    async with client(base_url, token) as c:
        me = (await c.call_tool("whoami", {})).data
    assert me["app_roles"] == ["SDLC.Reader"]


async def test_audit_records_decision_and_rule(base_url, entra, caplog):
    caplog.set_level("INFO", logger="sdlc.audit")
    token = entra.token(oid="aaaaaaaa-0000-0000-0000-00000000000a", groups=PERSONAS["payments_dev"])
    async with client(base_url, token) as c:
        await c.call_tool("review_code", {"repo": "payments-api"})
        with pytest.raises(ToolError):
            await c.call_tool("review_code", {"repo": "platform-infra"})
        with pytest.raises(ToolError):
            await c.call_tool("config_info", {})
    records = [json.loads(r.getMessage()) for r in caplog.records if r.name == "sdlc.audit"]
    records = [r for r in records if r["event"] == "tool_call"]
    assert [(r["decision"], r["outcome"]) for r in records] == [
        ("allow", "ok"),
        ("deny", "denied"),
        ("deny", "denied"),
    ]
    assert records[0]["teams"] == ["payments"]
    assert {"developer", "viewer", "signed-in"} <= set(records[0]["roles"])
    assert "teams/payments.yaml#policy/tools/constraints/review_code" in records[1]["matched_rule"]
    assert records[2]["matched_rule"] == "default-deny"
    assert all(
        "platform-infra"
        not in json.dumps({k: v for k, v in r.items() if k not in ("error", "reason")})
        for r in records
    )


def test_startup_fails_if_catalog_constrains_missing_parameter(config_dir, entra):
    import yaml

    tools = config_dir / "tools.yaml"
    doc = yaml.safe_load(tools.read_text())
    doc["tools"]["review_code"]["args"]["branch"] = {"type": "string"}  # not a tool parameter
    tools.write_text(yaml.safe_dump(doc))
    store = ConfigStore(lambda: load_snapshot(config_dir, "local", TEST_ENV))
    with pytest.raises(ValueError, match=r"review_code: args \['branch'\]"):
        build_server(store, entra.verifier())
