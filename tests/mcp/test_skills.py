"""Stage 4c: skills and agent context served per user by the MCP server (real HTTP)."""

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.support.entra import G_ENG_ALL, G_PAYMENTS_DEVS, G_PLATFORM_DEVS

G_PAYMENTS_LEADS = "SDLC.Payments.Approver"
G_PLATFORM_ADMINS = "SDLC.Admin"


def client(base_url, entra, groups):
    return Client(f"{base_url}/mcp", auth=entra.token(roles=groups))


async def skills_of(base_url, entra, groups) -> set[str]:
    async with client(base_url, entra, groups) as c:
        return {s["name"] for s in (await c.call_tool("list_skills", {})).data}


# every viewer: the Goldfish document flow and its lenses (version-03 P10)
EGM = {
    "egm-document-flow",
    "egm-brainstorm",
    "lens-zoom-out",
    "lens-comprehension",
    "lens-design-critic",
    "lens-implementation-readiness",
    "lens-structure",
    "lens-style",
}
# payments typed team skills (version-03 P10 G6)
PAYMENTS_TYPED = {"payments-pci-lens", "payments-story-questions", "payments-design-template"}
WEBAPP_ADDONS = {
    "webapp-coding-standards",
    "webapp-code-review",
    "webapp-api-lens",
    "webapp-design-template",
    "webapp-story-template",
}


@pytest.mark.parametrize(
    ("groups", "expected"),
    [
        ([G_ENG_ALL], {"write-user-story"} | EGM),
        (
            [G_ENG_ALL, G_PAYMENTS_DEVS],
            {"write-user-story", "test-case-gen", "pci-checklist"} | EGM | PAYMENTS_TYPED,
        ),
        (
            [G_ENG_ALL, G_PAYMENTS_LEADS],
            {
                "write-user-story",
                "test-case-gen",
                "pci-checklist",
                "design-review",
                "ledger-design-review",
            }
            | EGM
            | PAYMENTS_TYPED,
        ),
        (
            [G_ENG_ALL, G_PLATFORM_DEVS],
            {"write-user-story", "test-case-gen", "infra-change-review"} | EGM,
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
            }
            | EGM
            | PAYMENTS_TYPED
            | WEBAPP_ADDONS,
        ),
    ],
)
async def test_list_skills_per_persona(base_url, entra, groups, expected):
    assert await skills_of(base_url, entra, groups) == expected


async def test_list_skills_shows_tags_and_team(base_url, entra):
    async with client(base_url, entra, [G_ENG_ALL, G_PAYMENTS_DEVS]) as c:
        listed = {s["name"]: s for s in (await c.call_tool("list_skills", {})).data}
    assert listed["payments-pci-lens"]["tags"] == ["goldfish-lens"]
    assert listed["payments-pci-lens"]["team"] == "payments"
    assert listed["lens-zoom-out"]["tags"] == ["goldfish-lens"]
    assert "team" not in listed["lens-zoom-out"]  # global skill
    assert listed["pci-checklist"]["tags"] == []


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
        "payments": {"default_project": "payments", "glossary_source": "payments-code"}
    }
    assert [i["team"] for i in platform["instructions"]] == ["sdlc-platform"]
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
