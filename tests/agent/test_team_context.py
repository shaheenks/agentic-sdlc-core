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


async def test_real_fetch_as_the_user(base_url, entra):
    payments = await fetch_agent_context(
        f"{base_url}/mcp", entra.token(groups=[G_ENG_ALL, G_PAYMENTS_DEVS])
    )
    platform = await fetch_agent_context(
        f"{base_url}/mcp", entra.token(groups=[G_ENG_ALL, G_PLATFORM_DEVS])
    )
    assert [i["team"] for i in payments["instructions"]] == ["payments"]
    assert [i["team"] for i in platform["instructions"]] == ["platform"]
    prompt = render_team_context(payments)
    assert "pci-checklist" in prompt and "platform" not in prompt.lower()
