"""Stage 4d: the agent's per-session team context (sdlc_agent.with_team_context)."""

from sdlc_agent import render_team_context, with_team_context
from sdlc_agent.team_context import fetch_agent_context
from sdlc_auth.adk import reset_request_token, set_request_token

from tests.support.entra import G_ENG_ALL, G_PAYMENTS_DEVS, G_PLATFORM_DEVS

BASE = "You are an SDLC assistant."
PAYMENTS = {
    "instructions": [{"team": "payments", "source": "x.md", "text": "Mind PCI."}],
    "context": {"payments": {"default_project": "payments"}},
}


class Session:
    def __init__(self, sid):
        self.id = sid


class Ctx:
    def __init__(self, sid="s1", user="u1"):
        self.session, self.user_id, self.state = Session(sid), user, {}


def test_render():
    text = render_team_context(PAYMENTS)
    assert "### Team: payments\nMind PCI." in text
    assert "Context for team payments: default_project=payments" in text
    assert "does not grant access" in text
    assert render_team_context({"instructions": [], "context": {}}) == ""


async def test_provider_appends_context_and_caches_per_session():
    calls = []

    async def fake_fetch(url, token, session_id=None):
        calls.append((url, token, session_id))
        return PAYMENTS

    provider = with_team_context(BASE, "http://mcp/mcp", fetch=fake_fetch)
    reset = set_request_token("tok-1")
    try:
        first = await provider(Ctx("s1"))
        again = await provider(Ctx("s1"))
        other_session = await provider(Ctx("s2"))
    finally:
        reset_request_token(reset)
    assert first.startswith(BASE) and "Mind PCI." in first
    assert again == first and other_session == first
    # s1 cached; the conversation id travels with each fetch (correlation)
    assert calls == [("http://mcp/mcp", "tok-1", "s1"), ("http://mcp/mcp", "tok-1", "s2")]


async def test_no_user_token_means_base_instruction_only():
    async def must_not_fetch(url, token, session_id=None):
        raise AssertionError("fetched without a user token")

    provider = with_team_context(BASE, "http://mcp/mcp", fetch=must_not_fetch)
    assert await provider(Ctx()) == BASE


async def test_fetch_failure_falls_back_to_base(caplog):
    async def failing(url, token, session_id=None):
        raise ConnectionError("mcp down")

    provider = with_team_context(BASE, "http://mcp/mcp", fetch=failing)
    reset = set_request_token("tok")
    try:
        assert await provider(Ctx()) == BASE
    finally:
        reset_request_token(reset)
    assert "team context unavailable" in caplog.text


TEAMS = [
    {"name": "payments", "description": "Payment APIs"},
    {"name": "sdlc-platform", "description": "The platform"},
]
BROAD = {
    "team": None,
    "instructions": [
        {"team": "payments", "source": "p.md", "text": "Mind PCI."},
        {"team": "sdlc-platform", "source": "s.md", "text": "Terraform by the user."},
    ],
    "context": {"payments": {"default_project": "payments"}},
    "teams": TEAMS,
    "default_team": None,
}
FULL = {
    "team": "payments",
    "instructions": [{"team": "payments", "source": "p.md", "text": "Mind PCI."}],
    "context": {"payments": {"default_project": "payments"}},
    "teams": TEAMS,
    "flows": {
        "document": {
            "lenses": ["lens-zoom-out"],
            "max_lenses": 6,
            "max_rereviews": 1,
            "types": {
                "design": {"template": "payments-design-template", "required_lenses": ["pci"]}
            },
        }
    },
}


def test_broad_render_lists_teams_and_locks_none():
    text = render_team_context(BROAD)
    assert "No team is locked" in text and "set_active_team" in text
    assert "- payments: Payment APIs" in text and "- sdlc-platform: The platform" in text
    assert "Mind PCI." in text and "Terraform by the user." in text  # team guidance kept


def test_full_render_applies_one_team_and_names_the_others():
    text = render_team_context(FULL)
    assert "Locked team for this conversation: **payments**" in text
    assert "Mind PCI." in text and "Terraform" not in text
    assert "also a member of (not applied here):\n- sdlc-platform: The platform" in text
    assert "No team is locked" not in text
    assert (
        "- design: template: payments-design-template; required lenses (cannot be dropped): pci"
        in text
    )
    assert "Limits: max_lenses 6, max_rereviews 1" in text
    assert "Document flow defaults" not in render_team_context(BROAD | {"flows": FULL["flows"]})


def scripted_fetch(calls, refuse=()):
    from sdlc_agent.team_context import UnknownTeamError

    async def fetch(url, token, session_id=None, team=None):
        calls.append(team)
        if team in refuse:
            raise UnknownTeamError(team)
        return FULL if team == "payments" else BROAD

    return fetch


async def test_provider_follows_the_active_team_in_state():
    from sdlc_agent import ACTIVE_TEAM_KEY

    calls = []
    provider = with_team_context(BASE, "http://mcp/mcp", fetch=scripted_fetch(calls))
    ctx = Ctx("s1")
    reset = set_request_token("tok")
    try:
        before = await provider(ctx)
        ctx.state[ACTIVE_TEAM_KEY] = "payments"  # what set_active_team writes
        after = await provider(ctx)
        again = await provider(ctx)
    finally:
        reset_request_token(reset)
    assert "No team is locked" in before and "Locked team" in after and again == after
    assert calls == [None, "payments"]  # the active team is part of the cache key


async def test_a_team_the_user_left_falls_back_to_broad_and_says_so():
    from sdlc_agent import ACTIVE_TEAM_KEY

    calls = []
    provider = with_team_context(
        BASE, "http://mcp/mcp", fetch=scripted_fetch(calls, refuse={"payments"})
    )
    ctx = Ctx("s1")
    ctx.state[ACTIVE_TEAM_KEY] = "payments"
    reset = set_request_token("tok")
    try:
        text = await provider(ctx)
    finally:
        reset_request_token(reset)
    assert "No team is locked" in text
    assert "(payments) is no longer one of the user's teams" in text
    assert calls == ["payments", None]


async def test_set_active_team_checks_with_the_server_and_writes_state():
    from sdlc_agent import ACTIVE_TEAM_KEY, make_set_active_team

    calls = []
    tool = make_set_active_team("http://mcp/mcp", fetch=scripted_fetch(calls, refuse={"hr"}))
    ctx = Ctx("s1")
    reset = set_request_token("tok")
    try:
        refused = await tool.func(team="hr", tool_context=ctx)
        assert refused["status"] == "error" and ACTIVE_TEAM_KEY not in ctx.state
        done = await tool.func(team=" payments ", tool_context=ctx)
        assert done == {"status": "set", "team": "payments", "description": "Payment APIs"}
        assert ctx.state[ACTIVE_TEAM_KEY] == "payments"
        assert (await tool.func(team="", tool_context=ctx))["status"] == "cleared"
        assert ctx.state[ACTIVE_TEAM_KEY] is None
    finally:
        reset_request_token(reset)
    assert calls == ["hr", "payments"]
    no_user = await tool.func(team="payments", tool_context=Ctx())
    assert no_user["status"] == "error"


async def test_real_fetch_of_one_team_as_the_user(base_url, entra):
    import pytest
    from sdlc_agent.team_context import UnknownTeamError

    token = entra.token(roles=[G_ENG_ALL, G_PAYMENTS_DEVS, G_PLATFORM_DEVS])
    full = await fetch_agent_context(f"{base_url}/mcp", token, team="sdlc-platform")
    assert [i["team"] for i in full["instructions"]] == ["sdlc-platform"]
    payments_only = entra.token(roles=[G_ENG_ALL, G_PAYMENTS_DEVS])
    with pytest.raises(UnknownTeamError):
        await fetch_agent_context(f"{base_url}/mcp", payments_only, team="sdlc-platform")


async def test_real_fetch_as_the_user(base_url, entra):
    payments = await fetch_agent_context(
        f"{base_url}/mcp", entra.token(roles=[G_ENG_ALL, G_PAYMENTS_DEVS])
    )
    platform = await fetch_agent_context(
        f"{base_url}/mcp", entra.token(roles=[G_ENG_ALL, G_PLATFORM_DEVS])
    )
    assert [i["team"] for i in payments["instructions"]] == ["payments"]
    assert [i["team"] for i in platform["instructions"]] == ["sdlc-platform"]
    prompt = render_team_context(payments)
    assert "pci-checklist" in prompt and "sdlc-platform" not in prompt.lower()
