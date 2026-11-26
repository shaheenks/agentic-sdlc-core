"""ci_workflow_agent's workflows end to end in ADK, with a scripted model and a faked event_agent_mcp (FR-SDLC-006,
DEC-0015): a run follows its session's state, plans each target repository once with one fresh-context review, and
implements an approved plan or says on its pull request why it stopped."""

import json
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from ci_workflow_agent.agent import skill
from ci_workflow_agent.identity import EVENT, INPUTS, RUN, SUBSCRIPTION, SYSTEM_USER, TEAM, WORKFLOW, mcp_headers
from ci_workflow_agent.runtime import CiWorkflowApp, Refused, adk_app
from ci_workflow_agent.workflows import Kit, build_root
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.adk.tools.base_toolset import BaseToolset
from google.genai import types
from sdlc_adk import StepError

pytestmark = pytest.mark.anyio
ID = "F-20261126-refunds"
EVENT_TEXT = "SECRET-EVENT-PAYLOAD"


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Script(BaseLlm):
    """Answers by role, recognised from the system instruction."""

    model: str = "script"
    review: list[dict] = []
    implementation: dict = {}
    seen: list[tuple[str, str]] = []

    def role(self, instruction: str) -> str:
        if instruction.startswith("---") or "# Implementation plan" in instruction:
            return "reviser" if "You now revise" in instruction else "planner"
        if "# Implementation\n" in instruction:
            return "implementer"
        return "reviewer"

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator:
        role = self.role(str(llm_request.config.system_instruction or ""))
        text = " ".join(p.text for c in llm_request.contents for p in c.parts or [] if p.text)
        self.seen.append((role, text))
        answer = {
            "planner": "```markdown\n# PAY-1: plan for org/payments\n\n## Changes\n```",
            "reviser": "# PAY-1: plan for org/payments (revised)",
            "reviewer": json.dumps({"findings": self.review}),
            "implementer": json.dumps(self.implementation),
        }[role]
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=answer)]))


class NoTools(BaseToolset):
    async def get_tools(self, readonly_context=None):
        return []


class FakeMcp:
    def __init__(self):
        self.calls: list[tuple[str, dict, dict]] = []
        self.design_approved = True
        self.plan_approved = False
        self.targets = ["org/payments", "org/ledger"]
        self.open_plans: list[str] = []
        self.open_impl = False
        self.refuse_impl = False

    async def call(self, ctx: Any, name: str, arguments: dict | None = None) -> dict:
        arguments = arguments or {}
        self.calls.append((name, arguments, mcp_headers(ctx.state, None)))
        if name == "feature_status":
            design = {"approved": self.design_approved, "content": "# Design", "pull_request": 5}
            if not self.design_approved:
                design["reason"] = "merged by a system account (sdlc-bot), not a person"
            plan = {"approved": self.plan_approved, "content": "# Plan", "pull_request": 7}
            return {
                "branch": f"feature/{ID}",
                "artifacts": {"feature": {"approved": True, "content": "# Refunds"}, "design": design},
                "plans": {repo: dict(plan) for repo in self.targets},
                "jira_keys": ["PAY-1", "PAY-2"],
                "open_pull_requests": [{"kind": f"plan-{r.rsplit('/', 1)[-1]}"} for r in self.open_plans],
            }
        if name == "plan_open_pull_request":
            return {"pull_request": {"pull_request": len(self.calls), "url": "https://gh/pr/x"}}
        if name == "repo_pull_requests":
            branch = f"sdlc/{ID}/payments" if self.open_impl else "other"
            return {"pull_requests": [{"number": 9, "branch": branch, "url": "https://gh/pr/9"}]}
        if name == "implementation_open_pull_request":
            if self.refuse_impl:
                raise StepError("not_found", "push the change with workspace_run first")
            return {"pull_request": {"pull_request": 11, "url": "https://gh/pr/11"}}
        if name == "pull_request_comment":
            return {"url": "https://gh/pr/c"}
        raise AssertionError(name)

    def named(self, name: str) -> list[dict]:
        return [args for n, args, _ in self.calls if n == name]


@pytest.fixture
def world():
    script, mcp = Script(review=[], implementation={}, seen=[]), FakeMcp()
    kit = Kit(model=lambda: script, caller=mcp, toolset=lambda only=None: NoTools(), skill=skill)
    return script, mcp, InMemoryRunner(app=adk_app(build_root(kit)))


async def run(runner, workflow: str, inputs: dict, message: dict | None = None) -> dict:
    state = {
        TEAM: "payments",
        SUBSCRIPTION: f"ci_{workflow}",
        RUN: f"d-1:ci_{workflow}",
        WORKFLOW: workflow,
        INPUTS: inputs,
        EVENT: {"event_source": "github", "delivery_id": "d-1", "subject": "org/ctl#5"},
    }
    session = await runner.session_service.create_session(
        app_name="ci_workflow_agent", user_id=SYSTEM_USER, state=state
    )
    text = json.dumps(message or {"workflow": workflow, "inputs": inputs, "event": {"note": EVENT_TEXT}})
    outputs = []
    async for event in runner.run_async(
        user_id=SYSTEM_USER,
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=text)]),
    ):
        if event.author == "ci_workflow_agent" and getattr(event, "output", None) is not None:
            outputs.append(event.output)
    return outputs[-1]


async def test_a_merged_design_gets_one_reviewed_plan_per_target_repository(world):
    script, mcp, runner = world
    mcp.open_plans = ["org/ledger"]  # its plan pull request is open already: not drafted again
    result = await run(runner, "plan", {"control_id": ID})
    assert result["status"] == "done" and [p["repo"] for p in result["plans"]] == ["org/payments"]
    (opened,) = mcp.named("plan_open_pull_request")
    assert opened["repo"] == "org/payments" and opened["content"].startswith("# PAY-1: plan for org/payments")
    assert "found nothing serious" in opened["description"]
    _, _, headers = mcp.calls[0]
    assert headers["X-SDLC-Subscription"] == "ci_plan" and headers["X-SDLC-Event-Delivery"] == "d-1"
    roles = [r for r, _ in script.seen]
    assert roles == ["planner", "reviewer"]
    planner = next(t for r, t in script.seen if r == "planner")
    assert "# Design" in planner and "PAY-1" in planner and EVENT_TEXT not in planner  # the state, not the message
    reviewer = next(t for r, t in script.seen if r == "reviewer")
    assert "# Refunds" not in reviewer  # the reviewer sees the plan and the design only


async def test_serious_review_findings_are_applied_before_the_pull_request(world):
    script, mcp, runner = world
    mcp.targets = ["org/payments"]
    script.review = [
        {"severity": "major", "location": "Tests", "problem": "No test for PAY-2.", "suggestion": "Add one."}
    ]
    result = await run(runner, "plan", {"control_id": ID})
    (opened,) = mcp.named("plan_open_pull_request")
    assert (
        opened["content"] == "# PAY-1: plan for org/payments (revised)"
        and "1 serious findings applied" in opened["description"]
    )
    assert result["status"] == "done"
    reviser = next(t for r, t in script.seen if r == "reviser")
    assert "No test for PAY-2." in reviser


async def test_no_plan_from_a_design_a_person_did_not_merge(world):
    script, mcp, runner = world
    mcp.design_approved = False
    result = await run(runner, "plan", {"control_id": ID})
    assert result["code"] == "not_approved" and not mcp.named("plan_open_pull_request") and not script.seen
    (comment,) = mcp.named("pull_request_comment")
    assert comment["number"] == 5 and comment["repo"] == "control" and "system account" in comment["body"]


async def test_the_run_follows_its_state_not_its_message(world):
    _, mcp, runner = world
    result = await run(
        runner,
        "plan",
        {"control_id": ID},
        message={"workflow": "implement", "inputs": {"control_id": "F-20990101-other"}},
    )
    assert result["status"] == "done"
    assert all(args.get("control_id") == ID for _, args, _ in mcp.calls)


async def test_an_approved_plan_is_implemented_and_opened(world):
    script, mcp, runner = world
    mcp.plan_approved = True
    script.implementation = {
        "status": "ready",
        "title": "Refunds API",
        "summary": "Adds refund(); PAY-1, PAY-2.",
        "departures": "Kept the old name.",
    }
    result = await run(runner, "implement", {"control_id": ID, "repo": "payments"})
    assert result == {
        "status": "done",
        "repo": "org/payments",
        "pull_request": {"pull_request": 11, "url": "https://gh/pr/11"},
    }
    (opened,) = mcp.named("implementation_open_pull_request")
    assert opened["title"] == "Refunds API" and "Departures from the plan" in opened["description"]
    implementer = next(t for r, t in script.seen if r == "implementer")
    assert "# Plan" in implementer and "Read it at ref: feature/" in implementer


async def test_a_blocked_or_unpushed_implementation_says_why_on_the_plans_pull_request(world):
    script, mcp, runner = world
    mcp.plan_approved = True
    script.implementation = {"status": "blocked", "blocked_reason": "The plan names a module that does not exist."}
    result = await run(runner, "implement", {"control_id": ID, "repo": "payments"})
    assert result["status"] == "blocked" and not mcp.named("implementation_open_pull_request")
    (comment,) = mcp.named("pull_request_comment")
    assert comment["number"] == 7 and "does not exist" in comment["body"]
    mcp.refuse_impl, script.implementation = True, {"status": "ready", "summary": "x"}
    again = await run(runner, "implement", {"control_id": ID, "repo": "payments"})
    assert again["status"] == "blocked" and "workspace_run" in again["reason"]


async def test_nothing_is_implemented_twice_or_without_an_approved_plan(world):
    script, mcp, runner = world
    result = await run(runner, "implement", {"control_id": ID, "repo": "payments"})
    assert result["code"] == "not_approved"
    mcp.plan_approved, mcp.open_impl = True, True
    result = await run(runner, "implement", {"control_id": ID, "repo": "payments"})
    assert result["code"] == "already_open" and not script.seen
    assert (await run(runner, "implement", {"control_id": ID, "repo": "elsewhere"}))["code"] == "not_found"


def test_headers_carry_the_run_and_nothing_without_one():
    state = {TEAM: "payments", SUBSCRIPTION: "ci_plan", RUN: "d:ci_plan", EVENT: {"event_type": "pull_request.closed"}}
    headers = mcp_headers(state, None)
    assert headers["X-SDLC-Surface"] == "event_agents" and headers["X-SDLC-Event-Type"] == "pull_request.closed"
    tokens = type("T", (), {"get": lambda self: "id-token"})()
    assert mcp_headers(state, tokens)["Authorization"] == "Bearer id-token" and "X-SDLC-Surface" not in mcp_headers(
        state, tokens
    )
    assert mcp_headers({TEAM: "payments"}, None) == {}


async def test_the_runtime_takes_only_runs_of_the_system_user():
    app = CiWorkflowApp.__new__(CiWorkflowApp)
    good = {TEAM: "payments", SUBSCRIPTION: "ci_plan", RUN: "r", WORKFLOW: "plan"}
    with pytest.raises(Refused, match="belong to the user system"):
        await app.async_create_session(user_id="ada", state=good)
    with pytest.raises(Refused, match="state may hold only"):
        await app.async_create_session(user_id=SYSTEM_USER, state={**good, "sdlc_user_email": "x"})
    with pytest.raises(Refused, match="a run needs"):
        await app.async_create_session(user_id=SYSTEM_USER, state={TEAM: "payments"})
    with pytest.raises(Refused):
        async for _ in app.async_stream_query(message="x", user_id=SYSTEM_USER):
            pass
