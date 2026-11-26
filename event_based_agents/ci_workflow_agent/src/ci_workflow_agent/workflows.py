"""ci_workflow_agent's workflows, one ADK graph started per event (FR-SDLC-006, DEC-0013, DEC-0015).

The event gateway creates the run's session (team, subscription, workflow, inputs, event) and sends the event as the
message; the run follows the session's state, never the message's. No step waits for a person: approvals are the
merges that started the run, checked again by event_agent_mcp before every write.

- `plan` (a design merged into its feature branch): for each target repository without a plan, a drafter writes
  `plan-<repo>.md` from the design and the code, one fresh-context reviewer reads it, a reviser applies serious
  findings, and the plan is opened as a pull request into the feature branch.
- `implement` (a plan merged into its feature branch): an implementer writes the change with tests and builds it in
  the Code Workspace; when it is ready the implementation pull request is opened into the target repository's
  feature branch, and when it is blocked the reason is commented on the plan's pull request.

Deterministic steps call event_agent_mcp directly (sdlc_adk.McpCaller); drafting agents get read-only tools, and the
implementer also gets workspace_run. Every write is checked and recorded by the server."""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.workflow import START, FunctionNode, Workflow
from pydantic import BaseModel, Field
from sdlc_adk import StepError

from ci_workflow_agent.identity import INPUTS, WORKFLOW

READ_TOOLS = ["control_read_file", "repo_list", "repo_read_file"]
SERIOUS = ("blocker", "major")
FENCE = re.compile(r"^```[a-zA-Z]*\n(.*)\n```\s*$", re.S)
PLAN_READS = {"repo_read_file": 15, "repo_list": 8}
IMPLEMENT_READS = {"repo_read_file": 40, "repo_list": 15}
PLAN_REVIEWER = "review-readiness"  # one fresh-context review before the pull request (DEC-0015)


@dataclass
class Kit:
    model: Callable[[], Any]
    caller: Any
    toolset: Callable[[list[str]], Any]
    skill: Callable[[str], str]
    review_model: Callable[[], Any] | None = None

    def reviewer_model(self) -> Any:
        return (self.review_model or self.model)()


class RunIn(BaseModel):
    """The event gateway's message. Only a trigger: the run's facts are the session's state."""

    workflow: str = ""
    inputs: dict[str, str] = Field(default_factory=dict)
    event: dict[str, Any] = Field(default_factory=dict)
    resumed: bool = False


def _strip(text: Any) -> str:
    text = str(text or "").strip()
    match = FENCE.match(text)
    return match.group(1).strip() if match else text


def _node(func: Callable, name: str) -> FunctionNode:
    return FunctionNode(func=func, name=name)


def _stop(ctx: Context, reason: str, code: str = "stopped") -> dict[str, Any]:
    ctx.route = "stop"
    return {"status": "stopped", "code": code, "reason": reason}


def _inputs(ctx: Context) -> dict[str, str]:
    value = ctx.state.get(INPUTS)
    return value if isinstance(value, dict) else {}


def reading_budget(state_key: str, limits: dict[str, int]):
    """A before-tool callback refusing reads beyond `limits`; the count lives in the run's state."""

    def check(tool, args, tool_context):
        limit = limits.get(getattr(tool, "name", ""))
        if limit is None:
            return None
        used = dict(tool_context.state.get(state_key) or {})
        if used.get(tool.name, 0) >= limit:
            return {"error": "read_limit", "message": f"the reading budget ({limit} {tool.name} calls) is used up"}
        used[tool.name] = used.get(tool.name, 0) + 1
        tool_context.state[state_key] = used
        return None

    return check


def findings_of(text: Any) -> list[dict[str, str]]:
    try:
        data = json.loads(_strip(text))
        found = data.get("findings") if isinstance(data, dict) else None
    except (ValueError, TypeError):
        found = None
    out = []
    for f in found if isinstance(found, list) else []:
        if isinstance(f, dict):
            severity = f.get("severity") if f.get("severity") in ("blocker", "major", "nit") else "nit"
            out.append({"severity": severity, **{k: str(f.get(k, "")) for k in ("location", "problem", "suggestion")}})
    return out


DRAFT_RULES = """

You work inside an unattended workflow step: nobody can answer you. Work from the message and what you read with your
tools (the feature branch is the ref to read); put what you could not settle under Open questions. Your reads are
limited: read the files that matter, then write. Return only the Markdown document."""

REVIEWER_RULES = """

You review the document in the message, and nothing else. Return only the JSON your instructions describe."""


def _start(kit: Kit) -> FunctionNode:
    async def route(ctx: Context, node_input: RunIn):
        workflow = ctx.state.get(WORKFLOW)
        if workflow not in ("plan", "implement") or not _inputs(ctx).get("control_id"):
            return _stop(ctx, "the run names no known workflow or feature", "invalid_run")
        ctx.route = workflow
        return _inputs(ctx)

    return _node(route, "route")


# plan ------------------------------------------------------------------------------------------------------------


def plan_nodes(kit: Kit, end: FunctionNode) -> tuple[FunctionNode, list]:
    k = "ci:plan"
    reads = f"{k}:reads"

    async def status(ctx: Context, node_input: Any):
        control_id = _inputs(ctx)["control_id"]
        try:
            found = await kit.caller.call(ctx, "feature_status", {"control_id": control_id, "include_content": True})
        except StepError as exc:
            return _stop(ctx, f"cannot read {control_id}: {exc.message or exc.code}", exc.code)
        design = found["artifacts"]["design"]
        if not design.get("approved"):
            reason = design.get("reason") or "the design is not approved"
            if design.get("pull_request"):
                await _comment(kit, ctx, control_id, "control", design["pull_request"], f"No plan: {reason}.")
            return _stop(ctx, reason, "not_approved")
        opened = {p["kind"] for p in found.get("open_pull_requests") or [] if p.get("kind", "").startswith("plan-")}
        queue = [
            repo
            for repo, plan in (found.get("plans") or {}).items()
            if not plan.get("approved") and f"plan-{repo.rsplit('/', 1)[-1]}" not in opened
        ]
        ctx.state[f"{k}:queue"], ctx.state[f"{k}:results"] = queue, []
        ctx.state[f"{k}:context"] = {
            "control_id": control_id,
            "branch": found.get("branch"),
            "jira_keys": found.get("jira_keys") or [],
            "feature": found["artifacts"]["feature"].get("content", ""),
            "design": design.get("content", ""),
        }
        ctx.route = "next"
        return {"queued": queue, "already_open": sorted(opened)}

    async def next_(ctx: Context, node_input: Any):
        queue = list(ctx.state.get(f"{k}:queue") or [])
        if not queue:
            ctx.route = "done"
            return None
        repo, ctx.state[f"{k}:queue"] = queue[0], queue[1:]
        ctx.state[f"{k}:repo"], ctx.state[reads] = repo, {}
        c = ctx.state[f"{k}:context"]
        ctx.route = "draft"
        return (
            f"Repository: {repo}\nRead it at ref: {c['branch']}\nControl ID: {c['control_id']}\n"
            f"Jira keys: {', '.join(c['jira_keys']) or '-'}\n\n# Feature\n\n{c['feature']}\n\n# Design\n\n{c['design']}"
        )

    drafter = LlmAgent(
        name="plan_drafter",
        model=kit.model(),
        mode="single_turn",
        instruction=kit.skill("implementation-plan") + DRAFT_RULES,
        tools=[kit.toolset(READ_TOOLS)],
        before_tool_callback=reading_budget(reads, PLAN_READS),
    )

    async def to_review(ctx: Context, node_input: Any):
        ctx.state[f"{k}:plan"] = _strip(node_input)
        design = ctx.state[f"{k}:context"]["design"]
        return f"# Document to review\n\n{ctx.state[f'{k}:plan']}\n\n# What it must satisfy\n\n{design}"

    reviewer = LlmAgent(
        name="plan_reviewer",
        model=kit.reviewer_model(),
        mode="single_turn",
        instruction=kit.skill(PLAN_REVIEWER) + REVIEWER_RULES,
    )

    async def check(ctx: Context, node_input: Any):
        serious = [f for f in findings_of(node_input) if f["severity"] in SERIOUS]
        ctx.state[f"{k}:findings"] = serious
        if not serious:
            ctx.route = "open"
            return None
        ctx.route = "revise"
        listed = "\n".join(
            f"- ({f['severity']}, {f['location']}): {f['problem']} -> {f['suggestion']}" for f in serious
        )
        return (
            f"Revise the plan below. Apply these review findings:\n{listed}\n\n"
            f"Return only the complete revised Markdown plan.\n\n# Plan\n\n{ctx.state[f'{k}:plan']}"
        )

    reviser = LlmAgent(
        name="plan_reviser",
        model=kit.model(),
        mode="single_turn",
        instruction=kit.skill("implementation-plan")
        + "\n\nYou now revise an existing plan as the message asks. Keep everything else. Return only the Markdown.",
    )

    async def accept(ctx: Context, node_input: Any):
        ctx.state[f"{k}:plan"] = _strip(node_input)
        return None

    async def open_(ctx: Context, node_input: Any):
        c, repo = ctx.state[f"{k}:context"], ctx.state[f"{k}:repo"]
        findings = ctx.state.get(f"{k}:findings") or []
        notes = (
            f"One fresh-context review ({PLAN_REVIEWER}); {len(findings)} serious findings applied."
            if findings
            else f"One fresh-context review ({PLAN_REVIEWER}) found nothing serious."
        )
        results = list(ctx.state.get(f"{k}:results") or [])
        try:
            done = await kit.caller.call(
                ctx,
                "plan_open_pull_request",
                {
                    "control_id": c["control_id"],
                    "repo": repo,
                    "content": ctx.state[f"{k}:plan"],
                    "description": f"The implementation plan for {repo}. {notes}",
                },
            )
            results.append(
                {"repo": repo, **(done.get("pull_request") or {}), "already_open": bool(done.get("already_open"))}
            )
        except StepError as exc:
            results.append({"repo": repo, "error": exc.code, "message": exc.message})
        ctx.state[f"{k}:results"] = results
        return None

    async def done(ctx: Context, node_input: Any):
        results = ctx.state.get(f"{k}:results") or []
        failed = [r for r in results if r.get("error")]
        return {"status": "failed" if failed else "done", "plans": results}

    status_n, next_n, review_n, check_n = (
        _node(status, "plan_status"),
        _node(next_, "plan_next"),
        _node(to_review, "plan_to_review"),
        _node(check, "plan_check"),
    )
    accept_n, open_n, done_n = _node(accept, "plan_accept"), _node(open_, "plan_open"), _node(done, "plan_done")
    edges = [
        (status_n, {"next": next_n, "stop": end}),
        (next_n, {"draft": drafter, "done": done_n}),
        (drafter, review_n, reviewer, check_n),
        (check_n, {"revise": reviser, "open": open_n}),
        (reviser, accept_n, open_n),
        (open_n, next_n),
        (done_n, end),
    ]
    return status_n, edges


async def _comment(kit: Kit, ctx: Context, control_id: str, repo: str, number: int, body: str) -> None:
    try:
        await kit.caller.call(
            ctx, "pull_request_comment", {"control_id": control_id, "repo": repo, "number": number, "body": body}
        )
    except StepError:
        pass  # a comment that cannot be written does not change the run's outcome; the audit shows it


# implement -------------------------------------------------------------------------------------------------------

IMPLEMENT_RULES = """

You work inside an unattended workflow step: nobody can answer you. Read with your tools at the feature branch, build
with workspace_run, and end with the JSON your instructions describe."""


def implement_nodes(kit: Kit, end: FunctionNode) -> tuple[FunctionNode, list]:
    k = "ci:implement"
    reads = f"{k}:reads"

    async def status(ctx: Context, node_input: Any):
        inputs = _inputs(ctx)
        control_id, short = inputs["control_id"], inputs.get("repo", "")
        try:
            found = await kit.caller.call(ctx, "feature_status", {"control_id": control_id, "include_content": True})
        except StepError as exc:
            return _stop(ctx, f"cannot read {control_id}: {exc.message or exc.code}", exc.code)
        repo = next((r for r in found.get("plans") or {} if r.rsplit("/", 1)[-1].lower() == short.lower()), None)
        if repo is None:
            return _stop(ctx, f"{short} is not one of {control_id}'s target repositories", "not_found")
        plan = found["plans"][repo]
        if not plan.get("approved"):
            return _stop(ctx, plan.get("reason") or "the plan is not approved", "not_approved")
        branch = f"sdlc/{control_id}/{repo.rsplit('/', 1)[-1]}"
        try:
            open_prs = (await kit.caller.call(ctx, "repo_pull_requests", {"repo": repo})).get("pull_requests") or []
        except StepError as exc:
            return _stop(ctx, f"cannot list {repo}'s pull requests: {exc.message or exc.code}", exc.code)
        existing = next((p for p in open_prs if p.get("branch") == branch), None)
        if existing:
            return _stop(ctx, f"the implementation pull request is open already: {existing.get('url')}", "already_open")
        ctx.state[f"{k}:context"] = {
            "control_id": control_id,
            "repo": repo,
            "plan_pull_request": plan.get("pull_request"),
            "branch": found.get("branch"),
        }
        ctx.state[reads] = {}
        ctx.route = "go"
        return (
            f"Repository: {repo}\nRead it at ref: {found.get('branch')}\nControl ID: {control_id}\n"
            f"Jira keys: {', '.join(found.get('jira_keys') or []) or '-'}\n\n# Plan\n\n{plan.get('content', '')}\n\n"
            f"# Design\n\n{found['artifacts']['design'].get('content', '')}"
        )

    implementer = LlmAgent(
        name="implementer",
        model=kit.model(),
        mode="single_turn",
        instruction=kit.skill("implementation") + IMPLEMENT_RULES,
        tools=[kit.toolset([*READ_TOOLS, "workspace_run"])],
        before_tool_callback=reading_budget(reads, IMPLEMENT_READS),
    )

    async def finish(ctx: Context, node_input: Any):
        c = ctx.state[f"{k}:context"]
        try:
            report = json.loads(_strip(node_input))
        except (ValueError, TypeError):
            report = {}
        report = report if isinstance(report, dict) else {}
        if report.get("status") == "ready":
            description = str(report.get("summary") or "")
            if report.get("departures"):
                description += f"\n\n## Departures from the plan\n\n{report['departures']}"
            try:
                done = await kit.caller.call(
                    ctx,
                    "implementation_open_pull_request",
                    {
                        "control_id": c["control_id"],
                        "repo": c["repo"],
                        "title": str(report.get("title") or "")[:150] or f"{c['control_id']}: implementation",
                        "description": description,
                    },
                )
                return {"status": "done", "repo": c["repo"], "pull_request": done.get("pull_request")}
            except StepError as exc:
                reason = f"the implementation pull request could not be opened: {exc.message or exc.code}"
        else:
            reason = str(report.get("blocked_reason") or "the implementer gave no usable result")
        if c.get("plan_pull_request"):
            await _comment(
                kit, ctx, c["control_id"], "control", c["plan_pull_request"], f"Implementation stopped: {reason}"
            )
        return {"status": "blocked", "repo": c["repo"], "reason": reason}

    status_n, finish_n = _node(status, "implement_status"), _node(finish, "implement_finish")
    edges = [(status_n, {"go": implementer, "stop": end}), (implementer, finish_n, end)]
    return status_n, edges


def build_root(kit: Kit) -> Workflow:
    async def finish(ctx: Context, node_input: Any):
        return node_input

    end = _node(finish, "end")
    route = _start(kit)
    plan_first, plan_edges = plan_nodes(kit, end)
    implement_first, implement_edges = implement_nodes(kit, end)
    return Workflow(
        name="ci_workflow_agent",
        description="Plans and implements approved designs, one run per event (DEC-0015).",
        input_schema=RunIn,
        edges=[
            (START, route),
            (route, {"plan": plan_first, "implement": implement_first, "stop": end}),
            *plan_edges,
            *implement_edges,
        ],
    )
