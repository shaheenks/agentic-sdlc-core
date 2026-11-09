"""version-03 P10 G9: the caller's teams for the agent (get_agent_context(team=), resolve_team)."""

import dataclasses

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from sdlc_config import load_snapshot, resolve
from sdlc_core_mcp.team_tools import match_teams

from tests.support.entra import G_ENG_ALL, G_PAYMENTS_DEVS, G_PLATFORM_DEVS, TEST_ENV

BOTH = [G_ENG_ALL, G_PAYMENTS_DEVS, G_PLATFORM_DEVS]


async def call(base_url, entra, groups, tool, args):
    async with Client(f"{base_url}/mcp", auth=entra.token(groups=groups)) as c:
        return (await c.call_tool(tool, args)).data


async def test_agent_context_lists_own_teams_and_one_team_in_full(base_url, entra):
    broad = await call(base_url, entra, BOTH, "get_agent_context", {})
    assert [t["name"] for t in broad["teams"]] == ["payments", "sdlc-platform"]
    assert broad["teams"][0]["description"].startswith("Payment APIs")
    assert {i["team"] for i in broad["instructions"]} == {"payments", "sdlc-platform"}
    one = await call(base_url, entra, BOTH, "get_agent_context", {"team": "payments"})
    assert one["team"] == "payments"
    assert [i["team"] for i in one["instructions"]] == ["payments"]
    assert set(one["context"]) == {"payments"}
    assert len(one["teams"]) == 2  # still knows the other team exists ("also a member of")
    # G7: flow defaults: platform only without a team, plus the team's own with one
    assert broad["flows"]["document"]["types"] == {}
    design = one["flows"]["document"]["types"]["design"]
    assert design["required_lenses"] == ["payments-pci-lens"]


@pytest.mark.parametrize("team", ["sdlc-platform", "marketing"])
async def test_agent_context_of_a_team_you_are_not_in_is_unknown(base_url, entra, team):
    with pytest.raises(ToolError, match="unknown team") as exc:
        await call(
            base_url, entra, [G_ENG_ALL, G_PAYMENTS_DEVS], "get_agent_context", {"team": team}
        )
    assert team not in str(exc.value)  # same answer for both; no argument value in the error


async def test_one_team_user_resolves_without_a_question(base_url, entra):
    got = await call(base_url, entra, [G_ENG_ALL, G_PAYMENTS_DEVS], "resolve_team", {"hints": []})
    assert (got["result"], got["team"], got["reason"]) == ("team", "payments", "your only team")


async def test_a_hint_picks_one_of_two_teams_with_its_reason(base_url, entra):
    got = await call(
        base_url, entra, BOTH, "resolve_team", {"hints": ["retry logic in payments-api/refunds"]}
    )
    assert (got["result"], got["team"]) == ("team", "payments")
    assert "payments-api mentioned" in got["reason"]
    got = await call(
        base_url, entra, BOTH, "resolve_team", {"hints": ["github.com/x/agentic-sdlc-core"]}
    )
    assert got["team"] == "sdlc-platform"


async def test_ambiguous_and_none_ask_the_user(base_url, entra):
    both = await call(
        base_url, entra, BOTH, "resolve_team", {"hints": ["payments-ui", "agentic-sdlc-core"]}
    )
    assert both["result"] == "ambiguous" and both["team"] is None
    assert [c["team"] for c in both["candidates"]] == ["payments", "sdlc-platform"]
    nothing = await call(base_url, entra, BOTH, "resolve_team", {"hints": ["the login page"]})
    assert nothing["result"] == "none"
    assert [c["team"] for c in nothing["candidates"]] == ["payments", "sdlc-platform"]


async def test_hints_never_reveal_other_teams(base_url, entra):
    # a platform-only user names payments things: payments is not one of their teams
    got = await call(
        base_url,
        entra,
        [G_ENG_ALL, G_PLATFORM_DEVS],
        "resolve_team",
        {"hints": ["payments-api", "payments"]},
    )
    assert (got["result"], got["team"]) == ("team", "sdlc-platform")  # their only team
    assert "payments" not in str(got)
    viewer = await call(base_url, entra, [G_ENG_ALL], "resolve_team", {"hints": ["payments"]})
    assert viewer["result"] == "none" and viewer["candidates"] == []


def test_default_team_applies_only_when_no_hint_matches(config_dir):
    snap = load_snapshot(config_dir, "local", TEST_ENV)
    policy = dataclasses.replace(
        resolve(snap, ["eng-all", "payments-devs", "platform-devs"]), default_team="sdlc-platform"
    )
    assert match_teams(snap, policy, ["no names here"])["team"] == "sdlc-platform"
    assert match_teams(snap, policy, ["payments-ui"])["team"] == "payments"
