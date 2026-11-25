"""The workflows end to end in ADK, with a scripted model and a faked user_agent_mcp (FR-SDLC-002 to FR-SDLC-005,
FR-SDLC-004, FR-KNOW-004, DEC-0012): the chat agent starts a workflow, the workflow pauses for the user with
`adk_request_input`, and the answer resumes it."""

import json
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import pytest
from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.adk.tools.base_toolset import BaseToolset
from google.genai import types
from user_agent.agent import INSTRUCTION
from user_agent.identity import EMAIL_KEY, TEAM_KEY
from user_agent.mcp_client import McpCaller, StepError
from user_agent.runtime import adk_app
from user_agent.skills import skill
from user_agent.workflows import Kit, build_workflows

SECRET = "SECRET-CHAT-TEXT"
pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Script(BaseLlm):
    """Answers by role, recognised from the system instruction. The chat calls the tool named in `calls`."""

    model: str = "script"
    calls: dict[str, tuple[str, dict]] = {}
    design_findings: list[list[dict]] = []  # per review round, review-design's findings
    seen: list[tuple[str, list[str]]] = []

    def role(self, instruction: str) -> str:
        if instruction.startswith("You are user_agent"):
            return "chat"
        if "You now revise" in instruction:
            return "reviser"
        if "Draft from the message" in instruction:
            return "drafter"
        if "constructive sceptic" in instruction:
            return "review-design"
        return "reviewer"

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        role = self.role(str(llm_request.config.system_instruction or ""))
        texts = [p.text for c in llm_request.contents for p in c.parts or [] if p.text]
        self.seen.append((role, texts))
        last = llm_request.contents[-1].parts[0]
        if role == "chat":
            if last.text and last.text in self.calls:
                name, args = self.calls[last.text]
                part = types.Part(function_call=types.FunctionCall(name=name, args=args))
            else:
                part = types.Part(text="noted")
        elif role == "drafter":
            part = types.Part(text="```markdown\n# Feature: Refunds\n\n## User stories\n```")
        elif role == "reviser":
            part = types.Part(text="# Feature: Refunds (revised)")
        elif role == "review-design":
            n = sum(1 for r, _ in self.seen if r == "review-design")
            findings = self.design_findings[n - 1] if n <= len(self.design_findings) else []
            part = types.Part(text=json.dumps({"findings": findings}))
        else:
            part = types.Part(text='{"findings": []}')
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


class NoTools(BaseToolset):
    async def get_tools(self, readonly_context=None):
        return []


class FakeMcp:
    """user_agent_mcp as the workflows see it: records each call with the run's team."""

    def __init__(self):
        self.calls: list[tuple[str, dict, str | None]] = []
        self.approved = False
        self.jira_recorded = True

    async def call(self, ctx: Any, name: str, arguments: dict | None = None) -> dict:
        arguments = arguments or {}
        self.calls.append((name, arguments, ctx.state.get(TEAM_KEY)))
        if name == "team_systems":
            team = ctx.state.get(TEAM_KEY)
            if team == "risk":
                raise StepError("forbidden", "not a member of that team")
            return {"team": team, "teams": {team: {"repositories": [{"repo": "org/payments", "default": True}]}}}
        if name == "control_publish":
            control_id = arguments.get("control_id") or "F-20261125-refunds"
            return {"control_id": control_id, "pull_request": {"number": 1, "url": "https://gh/pr/1", "branch": "b"}}
        if name == "control_status":
            approval = {"path": "p", "published": True, "approved": self.approved}
            if self.approved:
                approval |= {"merged_by": "grace", "commit": "c1"}
            else:
                approval["reason"] = "the pull request is not merged"
            writes = [{"action": "create_feature", "results": {"feature": "PAY-1"}}] if self.jira_recorded else []
            return {
                "control_id": "F-20261125-refunds",
                "artifacts": {"feature": {**approval, "content": "# Feature: Refunds"}, "design": approval},
                "writes": writes,
                "jira_feature_recorded": self.jira_recorded,
            }
        if name == "jira_get_issue":
            return {"key": "PAY-1", "status": "In Design", "stories": []}
        if name == "jira_create_feature":
            return {"control_id": arguments["control_id"], "feature": {"key": "PAY-1"}, "stories": ["PAY-2"]}
        if name == "jira_link_design":
            return {"feature": "PAY-1"}
        raise AssertionError(name)

    def names(self) -> list[str]:
        return [name for name, _, _ in self.calls]


@pytest.fixture
def world():
    script, mcp = Script(calls={}, design_findings=[], seen=[]), FakeMcp()
    kit = Kit(model=lambda: script, caller=mcp, toolset=lambda only=None: NoTools(), skill=skill)
    chat = LlmAgent(name="user_agent", model=script, instruction=INSTRUCTION, tools=build_workflows(kit))
    runner = InMemoryRunner(app=adk_app(chat))
    return script, mcp, runner


async def start(runner, state: dict | None = None):
    return await runner.session_service.create_session(
        app_name="user_agent", user_id="u1", state={EMAIL_KEY: "ada@example.test", **(state or {})}
    )


async def turn(runner, session, *, text: str | None = None, answer: tuple[str, str] | None = None) -> dict:
    """One message (text, or the answer to a pending request); returns pending requests and tool results."""
    if text is not None:
        message = types.Content(role="user", parts=[types.Part(text=text)])
    else:
        interrupt, value = answer
        response = types.FunctionResponse(id=interrupt, name="adk_request_input", response={"result": value})
        message = types.Content(role="user", parts=[types.Part(function_response=response)])
    out = {"requests": [], "results": {}}
    async for event in runner.run_async(user_id="u1", session_id=session.id, new_message=message):
        for part in event.content.parts if event.content else []:
            if part.function_call and part.function_call.name == "adk_request_input":
                out["requests"].append((part.function_call.id, part.function_call.args))
            if part.function_response and part.function_response.name != "adk_request_input":
                out["results"][part.function_response.name] = part.function_response.response
    return out


async def state_of(runner, session) -> dict:
    found = await runner.session_service.get_session(app_name="user_agent", user_id="u1", session_id=session.id)
    return dict(found.state)


FEATURES = ("features_and_stories", {"team": "payments", "brief": "Refunds take two weeks; payers want days."})


async def test_review_findings_are_chosen_by_the_user_and_reviewers_never_see_the_chat(world):
    script, mcp, runner = world
    script.calls[f"{SECRET} draft it"] = FEATURES
    major = {"severity": "major", "location": "Stories", "problem": "No refund limit.", "suggestion": "Add one."}
    script.design_findings = [[major]]
    session = await start(runner)

    first = await turn(runner, session, text=f"{SECRET} draft it")
    ((interrupt, request),) = first["requests"]
    assert request["payload"]["kind"] == "review_findings" and request["payload"]["round"] == 1
    finding = request["payload"]["findings"][0]
    assert (finding["id"], finding["reviewer"], finding["severity"]) == ("F1", "review-design", "major")

    done = await turn(runner, session, answer=(interrupt, "all, and keep it short"))
    result = done["results"]["features_and_stories"]
    assert result["status"] == "drafted" and result["document"] == "# Feature: Refunds (revised)"
    assert result["rounds"] == 3 and result["open_findings"] == []  # revised, then two clean rounds
    assert (await state_of(runner, session))[TEAM_KEY] == "payments"
    assert mcp.calls[0] == ("team_systems", {}, "payments")
    reviewer_requests = [texts for role, texts in script.seen if role.startswith("review")]
    assert len(reviewer_requests) == 21 and all(SECRET not in " ".join(t) for t in reviewer_requests)
    assert all(SECRET not in " ".join(texts) for role, texts in script.seen if role in ("drafter", "reviser"))
    reviser = next(texts for role, texts in script.seen if role == "reviser")
    assert "F1" in reviser[-1] and "keep it short" in reviser[-1]


async def test_two_clean_rounds_finish_without_asking(world):
    script, _, runner = world
    script.calls["go"] = FEATURES
    session = await start(runner)
    done = await turn(runner, session, text="go")
    assert done["requests"] == [] and done["results"]["features_and_stories"]["rounds"] == 2


async def test_changing_the_chats_team_needs_confirmation(world):
    script, mcp, runner = world
    script.calls["go"] = FEATURES
    session = await start(runner, {TEAM_KEY: "platform"})
    ((interrupt, request),) = (await turn(runner, session, text="go"))["requests"]
    assert request["payload"] == {"kind": "team_scope", "from": "platform", "to": "payments"}
    stopped = (await turn(runner, session, answer=(interrupt, "no")))["results"]["features_and_stories"]
    assert stopped["status"] == "stopped" and (await state_of(runner, session))[TEAM_KEY] == "platform"
    assert mcp.calls == [] and not any(role == "drafter" for role, _ in script.seen)


async def test_a_team_the_user_is_not_in_is_refused_and_the_scope_restored(world):
    script, _, runner = world
    script.calls["go"] = ("features_and_stories", {"team": "risk", "brief": "x"})
    session = await start(runner)
    result = (await turn(runner, session, text="go"))["results"]["features_and_stories"]
    assert result["code"] == "forbidden"
    assert (await state_of(runner, session)).get(TEAM_KEY) is None  # the scope is restored
    assert not any(role == "drafter" for role, _ in script.seen)


PUBLISH = (
    "publish_feature",
    {
        "team": "payments",
        "content": "# Feature: Refunds",
        "summary": "Refunds",
        "feature": {"summary": "Refunds", "description": "Faster refunds"},
        "stories": [{"summary": "As a payer, I want a refund", "description": "Given..."}],
        "description": "No open findings.",
    },
)


async def test_jira_is_written_only_after_the_merge_is_approved(world):
    script, mcp, runner = world
    script.calls["add it to Jira"] = PUBLISH
    session = await start(runner)
    ((interrupt, request),) = (await turn(runner, session, text="add it to Jira"))["requests"]
    assert request["payload"]["kind"] == "merge_wait" and "https://gh/pr/1" in request["message"]
    assert mcp.names() == ["team_systems", "control_publish"]

    ((interrupt, again),) = (await turn(runner, session, answer=(interrupt, "merged")))["requests"]
    assert again["message"].startswith("Not approved yet") and "jira_create_feature" not in mcp.names()

    mcp.approved = True
    done = (await turn(runner, session, answer=(interrupt, "merged")))["results"]["publish_feature"]
    assert done["status"] == "done" and done["feature"]["key"] == "PAY-1" and done["approved_by"] == "grace"
    name, args, team = mcp.calls[-1]
    assert name == "jira_create_feature" and args["control_id"] == "F-20261125-refunds" and team == "payments"


async def test_cancelling_the_wait_writes_nothing(world):
    script, mcp, runner = world
    script.calls["add it to Jira"] = PUBLISH
    session = await start(runner)
    ((interrupt, _),) = (await turn(runner, session, text="add it to Jira"))["requests"]
    stopped = (await turn(runner, session, answer=(interrupt, "cancel")))["results"]["publish_feature"]
    assert stopped["code"] == "cancelled" and "jira_create_feature" not in mcp.names()


async def test_a_design_from_jira_starts_only_from_an_approved_feature(world):
    script, mcp, runner = world
    script.calls["design PAY-1"] = ("design_specification", {"team": "payments", "jira_key": "PAY-1"})
    session = await start(runner)
    refused = (await turn(runner, session, text="design PAY-1"))["results"]["design_specification"]
    assert refused["code"] == "not_approved" and not any(role == "drafter" for role, _ in script.seen)

    mcp.approved = True  # no Jira status is required (2026-11-25)
    done = (await turn(runner, session, text="design PAY-1"))["results"]["design_specification"]
    assert done["status"] == "drafted" and done["control_id"] == "F-20261125-refunds"
    assert done["repositories"] == ["org/payments"]  # the team's default
    drafter = next(texts for role, texts in script.seen if role == "drafter")
    assert "# Feature: Refunds" in drafter[-1]


async def test_a_design_from_the_users_own_feature_checks_nothing(world):
    script, mcp, runner = world
    script.calls["design mine"] = ("design_specification", {"team": "payments", "feature": "# My feature"})
    session = await start(runner)
    done = (await turn(runner, session, text="design mine"))["results"]["design_specification"]
    assert done["status"] == "drafted" and mcp.names() == ["team_systems"]


async def test_handing_off_a_design_links_it_to_the_jira_feature_after_the_merge(world):
    script, mcp, runner = world
    script.calls["hand it off"] = (
        "hand_off_design",
        {"team": "payments", "content": "# Design", "control_id": "F-20261125-refunds"},
    )
    session = await start(runner)
    ((interrupt, _),) = (await turn(runner, session, text="hand it off"))["requests"]
    mcp.approved = True
    done = (await turn(runner, session, answer=(interrupt, "merged")))["results"]["hand_off_design"]
    assert done["status"] == "handed_off" and done["jira_feature_linked"] == "PAY-1"
    publish = next(args for name, args, _ in mcp.calls if name == "control_publish")
    assert publish["kind"] == "design" and publish["control_id"] == "F-20261125-refunds"


async def test_the_mcp_caller_sends_the_sessions_user_and_team_and_maps_refusals():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        name = json.loads(request.content)["params"]["name"]
        if name == "control_status":
            body = {"error": "not_approved", "message": "merge it first"}
            content = [{"type": "text", "text": json.dumps(body)}]
            return httpx.Response(
                200, json={"jsonrpc": "2.0", "id": 1, "result": {"content": content, "isError": True}}
            )
        content = [{"type": "text", "text": json.dumps({"ok": True})}]
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"content": content}})

    class Ctx:
        class session:  # noqa: N801
            user_id = "1001"

        state = {EMAIL_KEY: "ada@example.test", TEAM_KEY: "payments"}

    caller = McpCaller("http://mcp/mcp", None, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert await caller.call(Ctx, "team_systems") == {"ok": True}
    headers = seen[0].headers
    assert (headers["x-sdlc-user-id"], headers["x-sdlc-team"], headers["mcp-name"]) == (
        "1001",
        "payments",
        "team_systems",
    )
    with pytest.raises(StepError) as refused:
        await caller.call(Ctx, "control_status", {"control_id": "F-1"})
    assert refused.value.code == "not_approved"


def test_reviewers_use_their_own_model_and_the_drafters_the_main_one():
    from google.adk.agents import LlmAgent as Agent

    main, fast = Script(calls={}, design_findings=[], seen=[]), Script(calls={}, design_findings=[], seen=[])
    kit = Kit(
        model=lambda: main,
        caller=FakeMcp(),
        toolset=lambda only=None: NoTools(),
        skill=skill,
        review_model=lambda: fast,
    )
    review = next(n for n in build_workflows(kit)[0].graph.nodes if n.name == "features_review")
    agents = {n.name: n.model for n in review.graph.nodes if isinstance(n, Agent)}
    assert agents["features_review_reviser"] is main
    assert all(model is fast for name, model in agents.items() if name.startswith("review_"))
