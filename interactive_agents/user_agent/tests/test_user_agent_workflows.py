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
    implementation: dict = {"status": "ready", "title": "Refunds API", "summary": "Adds refund().", "departures": ""}
    seen: list[tuple[str, list[str]]] = []

    def role(self, instruction: str) -> str:
        if instruction.startswith("You are user_agent"):
            return "chat"
        if "The build tool here is workspace_build" in instruction:
            return "implementer"
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
        elif role == "implementer":
            answered = any(p.function_response for c in llm_request.contents for p in c.parts or [])
            if not answered:
                changes = [{"path": "pkg/refunds.py", "content": f"round {len(self.seen)}"}]
                call = types.FunctionCall(
                    name="workspace_build",
                    args={"control_id": "F-20261125-refunds", "repo": "org/payments", "changes": changes},
                )
                part = types.Part(function_call=call)
            else:
                part = types.Part(text=json.dumps(self.implementation))
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


BUILDS: list[dict] = []


async def workspace_build(control_id: str, repo: str, changes: list[dict]) -> dict:
    """The Code Workspace, faked: passes every change."""
    BUILDS.append({"control_id": control_id, "repo": repo, "changes": changes})
    return {"ok": True, "built": True, "steps": [{"name": "test", "command": "pytest", "exit_code": 0, "seconds": 1}]}


class BuildTools(BaseToolset):
    def __init__(self, only):
        super().__init__()
        self.only = only or []

    async def get_tools(self, readonly_context=None):
        from google.adk.tools import FunctionTool

        return [FunctionTool(workspace_build)] if "workspace_build" in self.only else []


class FakeMcp:
    """user_agent_mcp as the workflows see it: records each call with the run's team."""

    def __init__(self):
        self.calls: list[tuple[str, dict, str | None]] = []
        self.approved = False
        self.jira_recorded = True
        self.open = False
        self.jira_refuses = False
        self.plan_approved = False
        self.saved: dict[str, str] = {}

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
            pr = {"number": 1, "url": "https://gh/pr/1", "branch": "b"}
            return {"control_id": control_id, "pull_request": pr, **({"already_open": True} if self.open else {})}
        if name == "control_status":
            approval = {"path": "p", "published": True, "approved": self.approved}
            if self.approved:
                approval |= {"merged_by": "grace", "commit": "c1"}
            else:
                approval["reason"] = "the pull request is not merged"
            writes = [{"action": "create_feature", "results": {"feature": "PAY-1"}}] if self.jira_recorded else []
            plan = {"path": "pp", "published": True, "approved": self.plan_approved, "content": "# Plan"}
            if not self.plan_approved:
                plan["reason"] = "the pull request is not merged"
            else:
                plan["merged_by"] = "grace"
            return {
                "control_id": "F-20261125-refunds",
                "branch": "feature/F-20261125-refunds",
                "plans": {"org/payments": plan},
                "target_repositories": ["org/payments"],
                "jira_keys": ["PAY-1", "PAY-2"],
                "artifacts": {
                    "feature": {**approval, "content": "# Feature: Refunds"},
                    "design": {**approval, "content": "# Design: Refunds"},
                },
                "writes": writes,
                "jira_feature_recorded": self.jira_recorded,
            }
        if name == "jira_search":
            return {"issues": [{"key": "PAY-5", "summary": "Payments 2027", "url": "https://x/PAY-5"}]}
        if name == "feature_open":
            control_id = arguments.get("control_id") or "F-20261126-refunds"
            return {"control_id": control_id, "branch": f"feature/{control_id}"}
        if name == "feature_target_branches":
            return {"control_id": arguments["control_id"], "repositories": {"org/payments": "created"}}
        if name == "jira_get_issue":
            return {"key": "PAY-1", "status": "In Design", "stories": []}
        if name == "jira_create_feature":
            if self.jira_refuses:
                raise StepError("downstream_invalid", "Jira answered 400 (invalid: issuetype)")
            epic = arguments["epic"].get("key") or "PAY-9"
            return {
                "control_id": arguments["control_id"],
                "epic": {"key": epic, "created": "key" not in arguments["epic"]},
                "feature": {"key": "PAY-1"},
                "stories": ["PAY-2"],
                "reused": [],
            }
        if name == "jira_link_design":
            return {"feature": "PAY-1"}
        if name == "plan_publish":
            pr = {"repo": arguments["repo"], "pull_request": 7, "url": "https://gh/pr/7"}
            return {"control_id": arguments["control_id"], "repo": arguments["repo"], "pull_request": pr}
        if name == "artifact_save":
            self.saved[arguments["name"]] = arguments["content"]
            return {"name": arguments["name"], "version": 1}
        if name == "artifact_read":
            if arguments["name"] not in self.saved:
                raise StepError("not_found", "no such artifact")
            return {"name": arguments["name"], "content": self.saved[arguments["name"]]}
        if name == "implementation_publish":
            return {"pull_request": {"pull_request": 11, "url": "https://gh/pr/11"}, "commit": "k1"}
        raise AssertionError(name)

    def names(self) -> list[str]:
        return [name for name, _, _ in self.calls]


@pytest.fixture
def world():
    script, mcp = Script(calls={}, design_findings=[], seen=[]), FakeMcp()
    BUILDS.clear()
    kit = Kit(model=lambda: script, caller=mcp, toolset=lambda only=None: BuildTools(only), skill=skill)
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
    assert result["rounds"] == 2 and result["open_findings"] == []  # revised, then one clean round
    assert (await state_of(runner, session))[TEAM_KEY] == "payments"
    assert mcp.calls[0] == ("team_systems", {}, "payments")
    reviewer_requests = [texts for role, texts in script.seen if role.startswith("review")]
    assert len(reviewer_requests) == 14 and all(SECRET not in " ".join(t) for t in reviewer_requests)
    assert all(SECRET not in " ".join(texts) for role, texts in script.seen if role in ("drafter", "reviser"))
    reviser = next(texts for role, texts in script.seen if role == "reviser")
    assert "F1" in reviser[-1] and "keep it short" in reviser[-1]


async def test_a_clean_round_finishes_without_asking(world):
    script, _, runner = world
    script.calls["go"] = FEATURES
    session = await start(runner)
    done = await turn(runner, session, text="go")
    assert done["requests"] == [] and done["results"]["features_and_stories"]["rounds"] == 1


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


def test_the_drafter_has_a_reading_budget():
    from user_agent.workflows import READ_LIMITS, reading_budget

    class Tool:
        def __init__(self, name):
            self.name = name

    class Ctx:
        state: dict = {}

    check = reading_budget("reads")
    for _ in range(READ_LIMITS["repo_read_file"]):
        assert check(Tool("repo_read_file"), {}, Ctx) is None
    refused = check(Tool("repo_read_file"), {}, Ctx)
    assert refused["error"] == "read_limit" and "write the draft" in refused["message"]
    assert check(Tool("knowledge_search"), {}, Ctx) is None  # searches are not counted
    assert check(Tool("repo_list"), {}, Ctx) is None


PUBLISH = (
    "publish_feature",
    {
        "team": "payments",
        "content": "# Feature: Refunds",
        "summary": "Refunds",
        "feature": {"summary": "Refunds", "description": "Faster refunds", "estimate": "M"},
        "stories": [{"summary": "As a payer, I want a refund", "description": "Given...", "story_points": 3}],
        "epic": {"summary": "Payments 2027 (new)", "description": "This year's payments work."},
    },
)


async def test_the_user_approves_the_feature_and_its_epic_then_branches_and_jira_follow(world):
    script, mcp, runner = world
    script.calls["add it to Jira"] = PUBLISH
    session = await start(runner)
    ((interrupt, request),) = (await turn(runner, session, text="add it to Jira"))["requests"]
    payload = request["payload"]
    assert payload["kind"] == "feature_approval" and payload["epics"][0]["key"] == "PAY-5"
    assert payload["proposed_epic"]["summary"] == "Payments 2027 (new)" and payload["stories"][0]["story_points"] == 3
    assert mcp.names() == ["team_systems", "jira_search"]  # nothing written before the approval
    assert mcp.calls[-1][1] == {"issue_type": "Epic", "open_only": True}

    done = (await turn(runner, session, answer=(interrupt, {"approve": True, "epic": "PAY-5"})))["results"]
    result = done["publish_feature"]
    assert result["status"] == "done" and result["branch"] == "feature/F-20261126-refunds"
    assert result["epic"]["key"] == "PAY-5" and result["target_branches"] == {"org/payments": "created"}
    assert mcp.names()[2:] == ["feature_open", "jira_create_feature", "feature_target_branches"]
    created = next(args for name, args, _ in mcp.calls if name == "jira_create_feature")
    assert created["epic"] == {"key": "PAY-5"} and created["stories"][0]["story_points"] == 3


async def test_the_proposed_epic_is_created_only_on_the_users_yes(world):
    script, mcp, runner = world
    script.calls["add it to Jira"] = PUBLISH
    session = await start(runner)
    ((interrupt, _),) = (await turn(runner, session, text="add it to Jira"))["requests"]
    await turn(runner, session, answer=(interrupt, {"approve": True, "create_epic": True}))
    created = next(args for name, args, _ in mcp.calls if name == "jira_create_feature")
    assert created["epic"] == {
        "summary": "Payments 2027 (new)",
        "description": "This year's payments work.",
        "create": True,
    }


async def test_rejecting_or_no_epic_writes_nothing(world):
    script, mcp, runner = world
    name, args = PUBLISH
    script.calls["add it to Jira"] = PUBLISH
    script.calls["no epic"] = (name, {**args, "epic": {}})
    session = await start(runner)
    ((interrupt, _),) = (await turn(runner, session, text="add it to Jira"))["requests"]
    stopped = (await turn(runner, session, answer=(interrupt, {"approve": False})))["results"]["publish_feature"]
    assert stopped["code"] == "not_approved"
    ((interrupt, _),) = (await turn(runner, session, text="no epic"))["requests"]
    stopped = (await turn(runner, session, answer=(interrupt, "yes")))["results"]["publish_feature"]
    assert stopped["code"] == "no_epic"
    assert not {"feature_open", "jira_create_feature"} & set(mcp.names())


async def test_a_jira_refusal_keeps_the_feature_and_a_retry_by_control_id_asks_nothing(world):
    script, mcp, runner = world
    name, args = PUBLISH
    script.calls["add it to Jira"] = PUBLISH
    script.calls["retry"] = (name, {**args, "control_id": "F-20261126-refunds", "epic": {"key": "PAY-5"}})
    mcp.jira_refuses = True
    session = await start(runner)
    ((interrupt, _),) = (await turn(runner, session, text="add it to Jira"))["requests"]
    stopped = (await turn(runner, session, answer=(interrupt, {"approve": True, "epic": "PAY-5"})))["results"]
    assert stopped["publish_feature"]["control_id"] == "F-20261126-refunds"
    assert "control_id F-20261126-refunds" in stopped["publish_feature"]["next"]

    mcp.jira_refuses = False
    done = await turn(runner, session, text="retry")
    assert done["requests"] == [] and done["results"]["publish_feature"]["status"] == "done"
    opened = [args for name, args, _ in mcp.calls if name == "feature_open"]
    assert opened[-1] == {"control_id": "F-20261126-refunds"}  # reused, not opened again


async def test_a_design_hand_off_needs_its_opened_feature(world):
    script, mcp, runner = world
    script.calls["hand it off"] = ("hand_off_design", {"team": "payments", "content": "# Design"})
    session = await start(runner)
    stopped = (await turn(runner, session, text="hand it off"))["results"]["hand_off_design"]
    assert stopped["code"] == "no_feature" and "control_publish" not in mcp.names()


# The implementation plan and the implementation with the user (DEC-0016) ----------------------------------------

ID = "F-20261125-refunds"


async def test_a_plan_is_drafted_only_from_a_merged_design_and_reviewed_by_the_readiness_reviewer(world):
    script, mcp, runner = world
    script.calls["plan it"] = ("implementation_plan", {"team": "payments", "control_id": ID})
    session = await start(runner)
    refused = (await turn(runner, session, text="plan it"))["results"]["implementation_plan"]
    assert refused["code"] == "not_approved" and not any(role == "drafter" for role, _ in script.seen)
    mcp.approved = True
    done = (await turn(runner, session, text="plan it"))["results"]["implementation_plan"]
    assert done["status"] == "drafted" and done["repo"] == "org/payments" and done["rounds"] == 1
    drafter = next(texts for role, texts in script.seen if role == "drafter")
    assert "# Design: Refunds" in drafter[-1] and "PAY-2" in drafter[-1]
    reviewers = [texts for role, texts in script.seen if role.startswith("review")]
    assert len(reviewers) == 1  # one fresh-context reviewer (review-readiness)
    mcp.plan_approved = True
    again = (await turn(runner, session, text="plan it"))["results"]["implementation_plan"]
    assert again["code"] == "already_done"


async def test_handing_off_a_plan_waits_for_a_persons_merge(world):
    script, mcp, runner = world
    script.calls["propose it"] = (
        "hand_off_plan",
        {"team": "payments", "control_id": ID, "repo": "org/payments", "content": "# Plan"},
    )
    session = await start(runner)
    ((interrupt, request),) = (await turn(runner, session, text="propose it"))["requests"]
    assert request["payload"]["kind"] == "merge_wait"
    ((interrupt, request),) = (await turn(runner, session, answer=(interrupt, "merged")))["requests"]
    assert "Not approved yet" in request["message"]  # not merged yet: back to waiting
    mcp.plan_approved = True
    done = (await turn(runner, session, answer=(interrupt, "merged")))["results"]["hand_off_plan"]
    assert done["status"] == "approved" and done["approved_by"] == "grace"
    assert mcp.names().count("plan_publish") == 1


async def test_an_approved_plan_is_built_shown_revised_kept_and_opened_as_the_user(world):
    script, mcp, runner = world
    script.calls["implement it"] = ("implementation", {"team": "payments", "control_id": ID, "repo": "payments"})
    script.calls["open it"] = ("open_implementation", {"team": "payments", "control_id": ID, "repo": "org/payments"})
    session = await start(runner)
    refused = (await turn(runner, session, text="implement it"))["results"]["implementation"]
    assert refused["code"] == "not_approved" and not BUILDS
    mcp.plan_approved = True
    ((interrupt, request),) = (await turn(runner, session, text="implement it"))["requests"]
    shown = request["payload"]
    assert shown["kind"] == "implementation_review" and shown["files"] == ["pkg/refunds.py"]
    assert shown["build"]["ok"] is True and shown["title"] == "Refunds API"
    implementer = next(texts for role, texts in script.seen if role == "implementer")
    assert "# Plan" in implementer[-1] and "Read it at ref: feature/" in implementer[-1]
    ((interrupt, _),) = (await turn(runner, session, answer=(interrupt, "add a test for partial refunds")))["requests"]
    second = [texts for role, texts in script.seen if role == "implementer"][-1]
    assert "add a test for partial refunds" in " ".join(second) and "The change so far" in " ".join(second)
    kept = (await turn(runner, session, answer=(interrupt, "ok")))["results"]["implementation"]
    assert kept["status"] == "built" and kept["artifact"] == f"implementation-{ID}-payments.json" and len(BUILDS) == 2
    saved = json.loads(mcp.saved[kept["artifact"]])
    assert saved["changes"] == BUILDS[-1]["changes"]  # the change last built is the one kept
    opened = (await turn(runner, session, text="open it"))["results"]["open_implementation"]
    assert opened["status"] == "opened" and opened["pull_request"]["pull_request"] == 11
    publish = next(args for name, args, _ in mcp.calls if name == "implementation_publish")
    assert publish["changes"] == BUILDS[-1]["changes"] and publish["title"] == "Refunds API"


async def test_a_blocked_implementation_keeps_nothing(world):
    script, mcp, runner = world
    mcp.plan_approved = True
    script.implementation = {"status": "blocked", "blocked_reason": "The plan names a module that does not exist."}
    script.calls["implement it"] = ("implementation", {"team": "payments", "control_id": ID, "repo": "org/payments"})
    session = await start(runner)
    done = (await turn(runner, session, text="implement it"))["results"]["implementation"]
    assert done["status"] == "blocked" and "does not exist" in done["reason"] and not mcp.saved
    script.calls["open it"] = ("open_implementation", {"team": "payments", "control_id": ID, "repo": "org/payments"})
    nothing = (await turn(runner, session, text="open it"))["results"]["open_implementation"]
    assert nothing["code"] == "not_found" and "implementation_publish" not in mcp.names()
