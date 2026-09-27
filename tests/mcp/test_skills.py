"""Stage 4c: skills and agent context served per user by the MCP server (real HTTP)."""

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.support.entra import G_ENG_ALL, G_PAYMENTS_DEVS, G_PLATFORM_DEVS

G_PAYMENTS_LEADS = "00000000-0000-0000-0000-000000000003"
G_PLATFORM_ADMINS = "00000000-0000-0000-0000-000000000005"


def client(base_url, entra, groups):
    return Client(f"{base_url}/mcp", auth=entra.token(groups=groups))


async def skills_of(base_url, entra, groups) -> set[str]:
    async with client(base_url, entra, groups) as c:
        return {s["name"] for s in (await c.call_tool("list_skills", {})).data}


@pytest.mark.parametrize(
    ("groups", "expected"),
    [
        ([G_ENG_ALL], {"write-user-story"}),
        ([G_ENG_ALL, G_PAYMENTS_DEVS], {"write-user-story", "test-case-gen", "pci-checklist"}),
        (
            [G_ENG_ALL, G_PAYMENTS_LEADS],
            {
                "write-user-story",
                "test-case-gen",
                "pci-checklist",
                "design-review",
                "ledger-design-review",
            },
        ),
        (
            [G_ENG_ALL, G_PLATFORM_DEVS],
            {"write-user-story", "test-case-gen", "infra-change-review"},
        ),
        (
            [G_ENG_ALL, G_PLATFORM_ADMINS],
            {
                "write-user-story",
                "test-case-gen",
                "design-review",
                "pci-checklist",
                "ledger-design-review",
                "infra-change-review",
            },
        ),
    ],
)
async def test_list_skills_per_persona(base_url, entra, groups, expected):
    assert await skills_of(base_url, entra, groups) == expected


async def test_hidden_skill_is_indistinguishable_from_unknown(base_url, entra):
    async with client(base_url, entra, [G_ENG_ALL, G_PLATFORM_DEVS]) as c:
        with pytest.raises(ToolError, match="unknown skill 'pci-checklist'"):
            await c.call_tool("load_skill", {"name": "pci-checklist"})
        with pytest.raises(ToolError, match="unknown skill 'does-not-exist'"):
            await c.call_tool("load_skill", {"name": "does-not-exist"})
        loaded = (await c.call_tool("load_skill", {"name": "infra-change-review"})).data
        assert "Blast radius" in loaded["instructions"]


async def test_agent_context_follows_teams(base_url, entra):
    async with client(base_url, entra, [G_ENG_ALL, G_PAYMENTS_DEVS]) as c:
        payments = (await c.call_tool("get_agent_context", {})).data
    async with client(base_url, entra, [G_ENG_ALL, G_PLATFORM_DEVS]) as c:
        platform = (await c.call_tool("get_agent_context", {})).data
    async with client(base_url, entra, [G_ENG_ALL]) as c:
        viewer = (await c.call_tool("get_agent_context", {})).data
    assert [i["team"] for i in payments["instructions"]] == ["payments"]
    assert "pci-checklist" in payments["instructions"][0]["text"]
    assert payments["context"] == {
        "payments": {"default_project": "payments", "glossary_source": "payments-docs"}
    }
    assert [i["team"] for i in platform["instructions"]] == ["platform"]
    assert "pci" not in platform["instructions"][0]["text"].lower()
    assert viewer["instructions"] == [] and viewer["context"] == {}


async def test_whoami_explain_includes_skills_and_agent_context(base_url, entra):
    async with client(base_url, entra, [G_ENG_ALL, G_PAYMENTS_DEVS]) as c:
        me = (await c.call_tool("whoami", {"explain": True})).data
    policy = me["policy"]
    assert policy["skills"]["pci-checklist"]["team"] == "payments"
    assert policy["skills"]["pci-checklist"]["granted_by"] == [
        "team:payments <- teams/payments.yaml#membership[0]"
    ]
    assert policy["agent_context"]["instructions"] == [
        {"team": "payments", "source": "skills/teams/payments/AGENT_ADDENDUM.md"}
    ]
