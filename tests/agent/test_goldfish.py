"""version-03 P10 G1: Goldfish reviews (sdlc_agent.goldfish) against the real test MCP server.

A scripted model plays the Elephant (calls goldfish_review once), each reviewer (calls the MCP
`whoami` tool, then answers JSON) and the synthesizer. No network beyond the local MCP server.
"""

import json
import re
from collections.abc import AsyncGenerator

import pytest
from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from sdlc_agent.goldfish import make_goldfish_review, synthesize
from sdlc_auth.adk import reset_request_token, set_request_token

from tests.support.entra import G_ENG_ALL, G_PAYMENTS_DEVS

DRAFT = "# Ledger retry design\n\nRetries use {backoff} with jitter."
PARENT_MARKER = "PARENT-HISTORY-ONLY"
STATE_SECRET = "parent-state-s3cr3t"
CONVERSATION = "conv-elephant-0001"


def audit(caplog) -> list[dict]:
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == "sdlc.audit"]


def text(response: str) -> AsyncGenerator[LlmResponse, None]:
    async def gen():
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=response)]))

    return gen()


def call(name: str, args: dict) -> AsyncGenerator[LlmResponse, None]:
    async def gen():
        part = types.Part(function_call=types.FunctionCall(name=name, args=args))
        yield LlmResponse(content=types.Content(role="model", parts=[part]))

    return gen()


class Script(BaseLlm):
    """Elephant, reviewers and synthesizer in one scripted model; records what each one saw."""

    lenses: list[str] = []
    seen: list[dict] = []
    synthesis: str | None = None  # None: merge everything into one finding
    reviewer_reply: str | None = None

    def generate_content_async(self, llm_request: LlmRequest, stream: bool = False):
        system = str(llm_request.config.system_instruction or "")
        contents = llm_request.contents or []
        parts = [p for c in contents for p in c.parts or []]
        answered = [p.function_response for p in parts if p.function_response]
        self.seen.append(
            {
                "system": system,
                "contents": str(contents),
                "tools": sorted(llm_request.tools_dict),
                "answered": answered,
            }
        )
        if "You merge review findings" in system:
            if self.synthesis is not None:
                return text(self.synthesis)
            ids = [f["id"] for f in json.loads(contents[-1].parts[0].text)]
            merged = {"title": "merged", "sources": ids + ["made-up#9"]}
            return text(json.dumps({"summary": "One problem.", "findings": [merged]}))
        if "Goldfish reviewer" in system:
            lens = re.search(r"## Lens: (\S+)", system).group(1)
            if "whoami" in llm_request.tools_dict and not answered:
                return call("whoami", {})
            if self.reviewer_reply is not None:
                return text(self.reviewer_reply)
            finding = {"severity": "Major" if "pci" in lens else "nit", "title": f"from {lens}"}
            return text(f"```json\n{json.dumps({'summary': lens, 'findings': [finding]})}\n```")
        # the Elephant
        if answered:
            return text("review done")
        return call("goldfish_review", {"draft": DRAFT, "lenses": self.lenses})


@pytest.fixture
def model():
    return Script(model="scripted", lenses=[], seen=[])


async def run_elephant(base_url, model, token, **options) -> dict:
    tool = make_goldfish_review(f"{base_url}/mcp", model, reviewer_tools=("whoami",), **options)
    elephant = LlmAgent(name="elephant", model=model, tools=[tool])
    sessions = InMemorySessionService()
    runner = Runner(app_name="elephant", agent=elephant, session_service=sessions)
    await sessions.create_session(
        app_name="elephant", user_id="oid-a", session_id=CONVERSATION, state={"note": STATE_SECRET}
    )
    reset = set_request_token(token)
    try:
        for prompt in (PARENT_MARKER, "please review it"):
            message = types.Content(role="user", parts=[types.Part(text=prompt)])
            async for _ in runner.run_async(
                user_id="oid-a", session_id=CONVERSATION, new_message=message
            ):
                pass
    finally:
        reset_request_token(reset)
        await runner.close()
    session = await sessions.get_session(
        app_name="elephant", user_id="oid-a", session_id=CONVERSATION
    )
    [result] = [
        p.function_response.response
        for e in session.events
        for p in (e.content.parts if e.content else [])
        if p.function_response and p.function_response.name == "goldfish_review"
    ]
    return result


def payments_dev(entra) -> str:
    return entra.token(groups=[G_ENG_ALL, G_PAYMENTS_DEVS])


async def test_isolated_reviewers_as_the_user_under_the_parent_conversation(
    base_url, entra, model, caplog
):
    caplog.set_level("INFO", logger="sdlc.audit")
    # pci-checklist: payments add-on; infra-change-review: sdlc-platform only (hidden here)
    model.lenses = ["pci-checklist", "write-user-story", "infra-change-review"]
    result = await run_elephant(base_url, model, payments_dev(entra))

    assert [(lens["lens"], lens["status"]) for lens in result["lenses"]] == [
        ("pci-checklist", "ok"),
        ("write-user-story", "ok"),
        ("infra-change-review", "unavailable"),
    ]
    # merged into one finding; the made-up source is ignored; severity = the highest it cites
    [merged] = result["findings"]["major"]
    assert merged["sources"] == ["pci-checklist#1", "write-user-story#1"]
    assert merged["lenses"] == ["pci-checklist", "write-user-story"]
    assert result["counts"] == {"blocker": 0, "major": 1, "nit": 0} and result["synthesized"]
    assert "## Major (1)" in result["report_markdown"]

    reviewers = [s for s in model.seen if "Goldfish reviewer" in s["system"]]
    assert len(reviewers) == 4  # two lenses: whoami call + answer each
    for seen in reviewers:
        # only the draft and the lens: no parent history, no parent state; braces stay literal
        assert "{backoff}" in seen["contents"]
        assert PARENT_MARKER not in seen["contents"] + seen["system"]
        assert STATE_SECRET not in seen["contents"] + seen["system"]
        assert seen["tools"] == ["whoami"]
    assert any("PCI" in s["system"] or "pci" in s["system"] for s in reviewers)

    records = audit(caplog)
    lens_access = {r["skill"]: r["decision"] for r in records if r["event"] == "skill_access"}
    assert lens_access == {
        "pci-checklist": "allow",
        "write-user-story": "allow",
        "infra-change-review": "deny",
    }
    whoami = [r for r in records if r["event"] == "tool_call" and r["tool"] == "whoami"]
    assert len(whoami) == 2 and {r["decision"] for r in whoami} == {"allow"}
    # every MCP call of the review: the user's identity, the parent conversation id
    review = [r for r in records if r["event"] in ("skill_access", "tool_call", "tools_list")]
    assert {r["agent_session_id"] for r in review} == {CONVERSATION}
    assert len({r["oid"] for r in review}) == 1


async def test_limits_and_bad_input(base_url, entra, model):
    model.lenses = ["a", "b", "c"]
    result = await run_elephant(base_url, model, payments_dev(entra), max_lenses=2)
    assert result == {"error": "at most 2 lenses per review"}

    model.seen.clear()
    model.lenses = ["Bad Name"]
    result = await run_elephant(base_url, model, payments_dev(entra))
    assert result["error"] == "invalid lens names"

    result = await run_elephant(base_url, model, payments_dev(entra), max_draft_chars=10)
    assert "too long" in result["error"]
    assert not [s for s in model.seen if "Goldfish reviewer" in s["system"]]


async def test_default_lenses_hidden_or_missing_are_unavailable(base_url, entra, model):
    result = await run_elephant(base_url, model, payments_dev(entra))
    assert {lens["status"] for lens in result["lenses"]} == {"unavailable"}
    assert len(result["lenses"]) == 4 and result["counts"] == {"blocker": 0, "major": 0, "nit": 0}


async def test_a_reviewer_with_unusable_output_is_failed_not_fatal(base_url, entra, model):
    model.lenses = ["write-user-story"]
    model.reviewer_reply = "I think it is fine."  # no JSON
    result = await run_elephant(base_url, model, payments_dev(entra))
    assert result["lenses"] == [{"lens": "write-user-story", "status": "failed"}]


async def test_reviewer_call_cap(base_url, entra, model):
    model.lenses = ["write-user-story"]
    result = await run_elephant(base_url, model, payments_dev(entra), max_llm_calls=1)
    assert result["lenses"][0]["status"] == "failed"  # needed two model calls


async def test_no_token_no_review(base_url, model):
    model.lenses = ["write-user-story"]
    result = await run_elephant(base_url, model, None)
    assert result == {"error": "not signed in"}


FINDINGS = [
    {
        "id": "x#1",
        "lens": "x",
        "severity": "nit",
        "title": "a",
        "detail": "",
        "where": "s1",
        "suggestion": "",
    },
    {
        "id": "y#1",
        "lens": "y",
        "severity": "blocker",
        "title": "b",
        "detail": "",
        "where": "",
        "suggestion": "",
    },
    {
        "id": "y#2",
        "lens": "y",
        "severity": "major",
        "title": "c",
        "detail": "",
        "where": "",
        "suggestion": "",
    },
]


async def test_synthesizer_output_is_validated(model):
    # x#1 cited twice (second use dropped), y#2 left out (kept as it was), bogus ids ignored
    model.synthesis = json.dumps(
        {
            "summary": "s",
            "findings": [
                {"title": "ab", "sources": ["x#1", "y#1"]},
                {"title": "dup", "sources": ["x#1"]},
                {"title": "ghost", "sources": ["nope#1"]},
            ],
        }
    )
    summary, merged = await synthesize(FINDINGS, model, "oid-a")
    assert summary == "s"
    assert [(m["title"], m["severity"], m["sources"]) for m in merged] == [
        ("ab", "blocker", ["x#1", "y#1"]),
        ("c", "major", ["y#2"]),
    ]

    model.synthesis = "not json"
    assert await synthesize(FINDINGS, model, "oid-a") is None
