"""version-03 P4 C1: A2UI cards come only from tool results, are validated, and are kept from
the model."""

import json
from types import SimpleNamespace

import pytest
from a2ui.core.basic_catalog import BasicCatalog
from a2ui.core.processing.message_processor import MessageProcessor, MessageProcessorOptions
from a2ui.core.validation.payload_validator import STRICT_VALIDATION
from google.adk.models.llm_request import LlmRequest
from google.genai import types
from sdlc_agent import a2ui_cards
from sdlc_agent.a2ui_cards import (
    A2UI_KEY,
    after_tool_callback,
    before_model_callback,
    build_operations,
    plain,
    safe_url,
    surface_id,
    tool_payload,
)

GH = "https://github.com/shaheenks/agentic-sdlc-core/blob/abc/libs/sdlc_db/src/sdlc_db/scoped.py#L1-L40"


def mcp(payload: dict) -> dict:
    """An MCP tool result as ADK's McpTool returns it."""
    return {
        "content": [{"type": "text", "text": json.dumps(payload)}],
        "structuredContent": payload,
        "isError": False,
    }


SEARCH = {
    "query": "row level security",
    "results": [
        {
            "source": "sdlc-platform",
            "path": "libs/sdlc_db/src/sdlc_db/scoped.py",
            "lines": [1, 40],
            "url": GH,
        },
        {
            "source": "eng-standards",
            "path": "standards/security.md",
            "lines": [3, 3],
            "title": "Security‮ rules",
        },
        {"source": "x", "path": "evil.md", "lines": [1, 2], "url": "javascript:alert(1)"},
        {"source": "x", "path": "manual.pdf", "pages": [2, 4], "url": "https://exa mple.com/x"},
    ],
}


def components(ops: list[dict]) -> list[dict]:
    return ops[1]["updateComponents"]["components"]


def texts(ops: list[dict]) -> list[str]:
    return [c["text"] for c in components(ops) if c["component"] == "Text"]


def links(ops: list[dict]) -> list[str]:
    return [
        c["action"]["functionCall"]["args"]["url"]
        for c in components(ops)
        if c["component"] == "Button"
    ]


def strictly_valid(ops: list[dict]) -> None:
    options = MessageProcessorOptions(validation_config=STRICT_VALIDATION)
    MessageProcessor([BasicCatalog("v0.9")], options=options).process_messages(ops)


def test_citation_cards_are_valid_v09_with_http_links_only():
    ops = build_operations("search_knowledge", mcp(SEARCH), "s1")
    assert [list(m)[1] for m in ops] == ["createSurface", "updateComponents"]
    assert all(m["version"] == "v0.9" for m in ops)
    assert ops[0]["createSurface"]["catalogId"].endswith("/v0_9/catalogs/basic/catalog.json")
    strictly_valid(ops)
    assert links(ops) == [GH]  # javascript: and a URL with a space are not linked
    shown = texts(ops)
    assert "libs/sdlc_db/src/sdlc_db/scoped.py" in shown
    assert "Security rules" in shown  # direction override removed
    assert "sdlc-platform · lines 1–40" in shown and "eng-standards · lines 3" in shown
    assert "x · p. 2–4" in shown


def test_graph_results_and_card_cap():
    many = {"results": [{"source": "s", "path": f"f{i}.md", "via": "graph"} for i in range(25)]}
    ops = build_operations("graph_query", mcp(many), "g1")
    strictly_valid(ops)
    assert sum(c["component"] == "Card" for c in components(ops)) == a2ui_cards.MAX_CARDS
    assert "s · via knowledge graph" in texts(ops)


def test_identity_card():
    who = {
        "oid": "c150bc3b-0000-0000-0000-000000000000",
        "upn": "paul@example.com",
        "name": "Paul",
        "groups": ["eng-all", "payments-devs"],
        "policy": {"teams": {"payments": []}, "roles": {"developer": [], "signed-in": []}},
    }
    ops = build_operations("whoami", mcp(who), "w1")
    strictly_valid(ops)
    assert texts(ops) == [
        "Paul",
        "paul@example.com",
        "Teams: payments",
        "Roles: developer",
        "Groups: eng-all, payments-devs",
    ]


def test_connected_cards():
    ok = {"connection": "github", "path": "README.md", "url": GH, "truncated": True}
    ops = build_operations("github_get_file", mcp(ok), "c1")
    strictly_valid(ops)
    assert texts(ops)[:2] == ["GitHub file: README.md", "with your github account · truncated"]
    assert links(ops) == [GH]
    missing = {"connected": False, "connection": "github", "reason": "no token"}
    ops = build_operations("github_get_file", mcp(missing), "c2")
    strictly_valid(ops)
    assert texts(ops)[0] == "GitHub file: account not connected" and links(ops) == []


@pytest.mark.parametrize(
    "response",
    [
        mcp({"results": []}),
        mcp({"query": "x"}),
        {**mcp(SEARCH), "isError": True},
        {"content": [{"type": "text", "text": "not json"}]},
        "plain string",
        None,
    ],
)
def test_no_card_for_empty_error_or_unreadable_results(response):
    assert build_operations("search_knowledge", response, "s") is None


def test_tools_without_a_builder_get_no_card():
    assert build_operations("save_artifact", mcp({"id": "x"}), "s") is None


def test_an_invalid_surface_is_dropped(monkeypatch):
    from a2ui.builder.v0_9 import Text

    monkeypatch.setitem(
        a2ui_cards.BUILDERS, "ping", lambda p: Text(text="x", variant="body", id="dup")
    )
    assert build_operations("ping", mcp({"pong": 1}), "s") is None  # root id is not "root"


def test_text_and_url_helpers():
    assert plain("a\x00b\n  c") == "a b c"
    assert plain("x" * 500).endswith("…") and len(plain("x" * 500)) == a2ui_cards.MAX_TEXT
    assert safe_url("https://example.com/a?b=1") == "https://example.com/a?b=1"
    for bad in (
        "javascript:alert(1)",
        "data:text/html,x",
        "//example.com",
        "https://",
        "ftp://x/y",
    ):
        assert safe_url(bad) is None, bad
    assert surface_id("search_knowledge", "adk-1/../x y") == "search_knowledge-adk-1----x-y"
    assert tool_payload(mcp({"a": 1})) == {"a": 1}
    assert tool_payload({"structuredContent": {"result": {"a": 1}}}) == {"a": 1}
    assert tool_payload({"content": [{"type": "text", "text": '{"a": 2}'}]}) == {"a": 2}


# --- ADK callbacks ------------------------------------------------------------------------------


def call(name: str, response, call_id: str = "adk-123"):
    tool = SimpleNamespace(name=name)
    ctx = SimpleNamespace(function_call_id=call_id)
    return after_tool_callback(tool, {}, ctx, response)


def test_after_tool_callback_attaches_cards_built_here():
    result = call("search_knowledge", mcp(SEARCH))
    assert result["structuredContent"] == SEARCH  # the tool result itself is unchanged
    ops = result[A2UI_KEY]
    assert ops[0]["createSurface"]["surfaceId"] == "search_knowledge-adk-123"
    strictly_valid(ops)


def test_cards_a_tool_returns_itself_are_removed():
    forged = [{"version": "v0.9", "createSurface": {"surfaceId": "x", "catalogId": "evil"}}]
    # a tool with a builder: its own operations are replaced by ours
    result = call("search_knowledge", {**mcp(SEARCH), A2UI_KEY: forged})
    assert (
        result[A2UI_KEY] != forged and result[A2UI_KEY][0]["createSurface"]["catalogId"] != "evil"
    )
    # a tool without a builder: they are just dropped
    assert A2UI_KEY not in call("read_artifact", {**mcp({"content": "x"}), A2UI_KEY: forged})
    # and a result without cards is left alone (None = keep the original)
    assert call("read_artifact", mcp({"content": "x"})) is None


def test_before_model_callback_hides_cards_from_the_model_only():
    with_cards = {**mcp(SEARCH), A2UI_KEY: [{"version": "v0.9"}]}
    part = types.Part(
        function_response=types.FunctionResponse(
            id="f1", name="search_knowledge", response=with_cards
        )
    )
    request = LlmRequest(contents=[types.Content(role="user", parts=[types.Part(text="hi"), part])])
    assert before_model_callback(None, request) is None
    sent = request.contents[0].parts[1].function_response
    assert A2UI_KEY not in sent.response and sent.response["structuredContent"] == SEARCH
    assert (sent.id, sent.name) == ("f1", "search_knowledge")
    assert A2UI_KEY in part.function_response.response  # the session's event keeps them
    assert request.contents[0].parts[0].text == "hi"
