"""The SDLC workflows of user_agent, as ADK graph workflows the chat agent calls as tools (FR-SDLC-002 to
FR-SDLC-005, DEC-0012).

- `features_and_stories` and `design_specification` draft with a stage skill and run the fresh-context review loop
  (FR-SDLC-004). Their drafts stay the user's own: nothing is checked on, or written to, another system.
- `publish_feature` and `hand_off_design` run only when the user asks for a write: they open the pull request on
  the team's control repository, wait until a person has merged it, check the approval through user_agent_mcp, and
  then write (Jira issues) or hand on (the merge starts ci_workflow_agent).
- Every workflow starts by setting the run's team scope (FR-KNOW-004); changing a chat's team needs the user's
  confirmation.

Each pause for the user is an ADK `RequestInput`; the chat answers it and the workflow continues. Deterministic
steps call user_agent_mcp directly (`McpCaller`), so approvals are checked by the server, never by a prompt.
Reviewers are single-turn agents that receive only the document (and the stories it must satisfy), never the
conversation."""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.events import RequestInput
from google.adk.workflow import START, FunctionNode, JoinNode, Workflow
from pydantic import BaseModel, Field

from user_agent.identity import TEAM_KEY
from user_agent.mcp_client import StepError

READ_TOOLS = [
    "knowledge_search",
    "knowledge_graph",
    "team_systems",
    "jira_get_issue",
    "jira_search",
    "repo_list",
    "repo_read_file",
]
REVIEWERS = (
    "review-structure",
    "review-style",
    "review-clarity",
    "review-design",
    "review-readiness",
    "review-technical-detail",
    "review-simplicity",
)
SERIOUS = ("blocker", "major")
CLEAN_ROUNDS = 2  # stop after two clean rounds in a row
REVIEWERS_AT_ONCE = 3  # parallel reviewer calls, to soften bursts against the model's capacity
ASK_AT_ROUND = 5  # from the fifth round, ask whether to go on
FENCE = re.compile(r"^```[a-zA-Z]*\n(.*)\n```\s*$", re.S)


@dataclass
class Kit:
    """What the workflows need: a model per agent, user_agent_mcp for the deterministic steps, a read-only toolset
    for drafting and reviewing agents, and the skills."""

    model: Callable[[], Any]
    caller: Any
    toolset: Callable[[list[str]], Any]
    skill: Callable[[str], str]


# Inputs -------------------------------------------------------------------------------------------------------


class FeaturesIn(BaseModel):
    team: str = Field(description="One of the user's teams; the run works in its scope.")
    brief: str = Field(description="The brief or idea: problem, users, scope, constraints, success, open questions.")


class DesignIn(BaseModel):
    team: str
    feature: str = Field("", description="The user's own feature artifact (Markdown), when it is not published.")
    jira_key: str = Field("", description="Or a Jira feature created from the team's control repository.")
    control_id: str = Field("", description="Or the control ID of a published feature.")
    repositories: list[str] = Field(default_factory=list, description="Target repositories; the team default if empty.")
    notes: str = ""


class Item(BaseModel):
    summary: str
    description: str = ""


class PublishFeatureIn(BaseModel):
    team: str
    content: str = Field(description="The feature and stories as reviewed (Markdown).")
    summary: str = Field(description="A few words naming the feature.")
    feature: Item
    stories: list[Item]
    project: str = Field("", description="A Jira project of the team; its default if empty.")
    description: str = Field("", description="Pull request text: review findings and what the user decided.")


class HandOffIn(BaseModel):
    team: str
    content: str = Field(description="The design specification as reviewed (Markdown).")
    control_id: str = Field("", description="The published feature it is for.")
    feature: str = Field("", description="Or the feature's Markdown, when the feature is not published.")
    summary: str = ""
    jira_keys: list[str] = Field(default_factory=list)
    description: str = ""


class ReviewIn(BaseModel):
    document: str
    context: str = ""


# Helpers ------------------------------------------------------------------------------------------------------


def _answer(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("result", value.get("answer", value))
    return value if isinstance(value, str) else json.dumps(value)


def _yes(value: Any) -> bool:
    return _answer(value).strip().lower() in ("yes", "y", "ok", "switch", "confirm", "true")


def _strip(text: Any) -> str:
    text = str(text or "").strip()
    match = FENCE.match(text)
    return match.group(1).strip() if match else text


def _stop(ctx: Context, reason: str, code: str = "stopped") -> dict[str, Any]:
    ctx.route = "stop"
    return {"status": "stopped", "code": code, "reason": reason}


def _node(func: Callable, name: str) -> FunctionNode:
    return FunctionNode(func=func, name=name)


def _end(name: str) -> FunctionNode:
    async def end(ctx: Context, node_input: Any):
        return node_input

    return _node(end, name)


# The team scope -----------------------------------------------------------------------------------------------


def scope_nodes(kit: Kit, prefix: str, model: type[BaseModel]):
    """scope -> (confirm -> apply) -> go. Sets the run's team, after confirming a change of the chat's team, and
    checks with user_agent_mcp that the user is in it."""
    key = f"sdlc_wf:{prefix}:input"

    async def enter(ctx: Context, team: str) -> dict[str, Any]:
        previous = ctx.state.get(TEAM_KEY)
        ctx.state[TEAM_KEY] = team
        try:
            systems = await kit.caller.call(ctx, "team_systems")
        except StepError as exc:
            ctx.state[TEAM_KEY] = previous
            return _stop(ctx, f"cannot work for team {team}: {exc.message or exc.code}", exc.code)
        ctx.route = "go"
        return {"team": team, "systems": (systems.get("teams") or {}).get(team) or {}, **ctx.state[key]}

    async def scope(ctx: Context, node_input: model):  # type: ignore[valid-type]
        data = node_input.model_dump()
        ctx.state[key] = data
        current = ctx.state.get(TEAM_KEY)
        if current and data["team"] != current:
            ctx.route = "confirm"
            return {"from": current, "to": data["team"]}
        return await enter(ctx, data["team"])

    async def confirm(ctx: Context, node_input: Any):
        yield RequestInput(
            message=(
                f"This chat works in team {node_input['from']}'s scope. Switch it to {node_input['to']}? "
                "Answer yes or no."
            ),
            payload={"kind": "team_scope", **node_input},
        )

    async def apply(ctx: Context, node_input: Any):
        if not _yes(node_input):
            return _stop(ctx, "the user kept the chat's current team")
        return await enter(ctx, ctx.state[key]["team"])

    return (
        _node(scope, f"{prefix}_scope"),
        _node(confirm, f"{prefix}_confirm_team"),
        _node(apply, f"{prefix}_switch_team"),
    )


def with_scope(kit: Kit, prefix: str, model: type[BaseModel], first: Any, end: Any) -> list:
    scope, confirm, apply = scope_nodes(kit, prefix, model)
    return [
        (START, scope),
        (scope, {"go": first, "confirm": confirm, "stop": end}),
        (confirm, apply),
        (apply, {"go": first, "stop": end}),
    ]


# The review loop ----------------------------------------------------------------------------------------------

REVIEWER_RULES = """

You review the document in the message, and nothing else: you do not see, and must not ask about, the conversation
that produced it. Return only the JSON your instructions describe."""


def _findings(name: str, text: Any) -> list[dict[str, Any]]:
    try:
        data = json.loads(_strip(text))
        found = data.get("findings") if isinstance(data, dict) else None
    except (ValueError, TypeError):
        found = None
    if not isinstance(found, list):
        return [
            {"reviewer": name, "severity": "nit", "location": "-", "problem": "unreadable review", "suggestion": "-"}
        ]
    out = []
    for f in found:
        if isinstance(f, dict):
            severity = f.get("severity") if f.get("severity") in ("blocker", "major", "nit") else "nit"
            out.append(
                {
                    "reviewer": name,
                    "severity": severity,
                    **{k: str(f.get(k, "")) for k in ("location", "problem", "suggestion")},
                }
            )
    return out


def review_workflow(kit: Kit, kind: str, drafting_skill: str) -> Workflow:
    """Reviewers in parallel, findings merged; clean rounds repeat until two in a row; otherwise the user chooses
    which findings to apply, a reviser applies them, and the next round starts. From round five the user is asked
    whether to go on."""
    p = f"{kind}_review"
    k = f"sdlc_wf:{p}"

    async def begin(ctx: Context, node_input: ReviewIn):
        ctx.state[f"{k}:doc"], ctx.state[f"{k}:context"] = _strip(node_input.document), node_input.context
        ctx.state[f"{k}:round"], ctx.state[f"{k}:clean"], ctx.state[f"{k}:findings"] = 0, 0, []
        return ctx.state[f"{k}:doc"]

    async def round_(ctx: Context, node_input: Any):
        ctx.state[f"{k}:round"] = ctx.state.get(f"{k}:round", 0) + 1
        context = ctx.state.get(f"{k}:context") or ""
        text = f"# Document to review\n\n{ctx.state[f'{k}:doc']}"
        return text + (f"\n\n# What it must satisfy\n\n{context}" if context else "")

    reviewers = tuple(
        LlmAgent(
            name=name.replace("-", "_"),
            model=kit.model(),
            mode="single_turn",
            instruction=kit.skill(name) + REVIEWER_RULES,
            tools=[kit.toolset(READ_TOOLS)],
        )
        for name in REVIEWERS
    )
    join = JoinNode(name=f"{p}_join")

    async def merge(ctx: Context, node_input: Any):
        findings = []
        for name, text in sorted((node_input or {}).items()):
            findings += _findings(name.replace("_", "-"), text)
        for i, f in enumerate(findings, 1):
            f["id"] = f"F{i}"
        serious = [f for f in findings if f["severity"] in SERIOUS]
        ctx.state[f"{k}:findings"] = findings
        ctx.state[f"{k}:clean"] = 0 if serious else ctx.state.get(f"{k}:clean", 0) + 1
        if not serious:
            ctx.route = "done" if ctx.state[f"{k}:clean"] >= CLEAN_ROUNDS else "again"
        else:
            ctx.route = "ask"
        return {"round": ctx.state[f"{k}:round"], "findings": findings}

    async def ask(ctx: Context, node_input: Any):
        n = ctx.state[f"{k}:round"]
        message = (
            f"Review round {n}: {len(node_input['findings'])} findings. Reply with the IDs to apply (or 'all'), with "
            "any changes of your own, or 'stop' to keep the document as it is."
        )
        if n >= ASK_AT_ROUND:
            message = f"This is review round {n}. " + message
        yield RequestInput(message=message, payload={"kind": "review_findings", **node_input})

    async def decide(ctx: Context, node_input: Any):
        answer = _answer(node_input).strip()
        if answer.lower() in ("stop", "none", "done", "no", ""):
            ctx.route = "done"
            return None
        findings = ctx.state[f"{k}:findings"]
        ids = set(re.findall(r"\bF\d+\b", answer))
        chosen = findings if answer.lower().startswith("all") else [f for f in findings if f["id"] in ids]
        ctx.route = "revise"
        listed = "\n".join(
            f"- {f['id']} ({f['severity']}, {f['location']}): {f['problem']} -> {f['suggestion']}" for f in chosen
        )
        return (
            "Revise the document below. Apply these review findings:\n"
            f"{listed or '- (none chosen)'}\n\nThe user's instructions: {answer}\n\n"
            "Return only the complete revised Markdown document.\n\n"
            f"# Document\n\n{ctx.state[f'{k}:doc']}"
        )

    reviser = LlmAgent(
        name=f"{p}_reviser",
        model=kit.model(),
        mode="single_turn",
        instruction=kit.skill(drafting_skill)
        + "\n\nYou now revise an existing draft as the message asks. Keep everything else as it is. Return only the "
        "complete Markdown document; do not save it.",
        tools=[kit.toolset(READ_TOOLS)],
    )

    async def accept(ctx: Context, node_input: Any):
        ctx.state[f"{k}:doc"], ctx.state[f"{k}:clean"] = _strip(node_input), 0
        return ctx.state[f"{k}:doc"]

    async def done(ctx: Context, node_input: Any):
        findings = ctx.state.get(f"{k}:findings") or []
        return {
            "document": ctx.state[f"{k}:doc"],
            "rounds": ctx.state.get(f"{k}:round", 0),
            "open_findings": findings if ctx.state.get(f"{k}:clean", 0) < CLEAN_ROUNDS else [],
        }

    begin_n, round_n, merge_n = _node(begin, f"{p}_begin"), _node(round_, f"{p}_round"), _node(merge, f"{p}_merge")
    ask_n, decide_n, accept_n, done_n = (
        _node(ask, f"{p}_ask"),
        _node(decide, f"{p}_decide"),
        _node(accept, f"{p}_accept"),
        _node(done, f"{p}_done"),
    )
    return Workflow(
        name=p,
        input_schema=ReviewIn,
        max_concurrency=REVIEWERS_AT_ONCE,
        edges=[
            (START, begin_n, round_n),
            (round_n, reviewers),
            (reviewers, join),
            (join, merge_n),
            (merge_n, {"again": round_n, "ask": ask_n, "done": done_n}),
            (ask_n, decide_n),
            (decide_n, {"revise": reviser, "done": done_n}),
            (reviser, accept_n, round_n),
        ],
    )


# Drafting workflows -------------------------------------------------------------------------------------------

DRAFT_RULES = """

You work inside a workflow step: you cannot ask the user anything. Draft from the message and from what you find with
your tools; put what you could not settle under Open questions. Return only the Markdown document; do not save it."""


def features_and_stories(kit: Kit) -> Workflow:
    p = "features"

    async def prompt(ctx: Context, node_input: Any):
        return f"Team: {node_input['team']}\n\n# Brief\n\n{node_input['brief']}"

    drafter = LlmAgent(
        name=f"{p}_drafter",
        model=kit.model(),
        mode="single_turn",
        instruction=kit.skill("features-and-stories") + DRAFT_RULES,
        tools=[kit.toolset(READ_TOOLS)],
    )

    async def to_review(ctx: Context, node_input: Any):
        return {"document": _strip(node_input), "context": ""}

    async def finish(ctx: Context, node_input: Any):
        return {
            "status": "drafted",
            "team": ctx.state.get(TEAM_KEY),
            **node_input,
            "next": "Save the draft with artifact_save and show it. It stays the user's own; when the user asks to "
            "add it to Jira, call publish_feature.",
        }

    prompt_n, end = _node(prompt, f"{p}_prompt"), _end(f"{p}_end")
    return Workflow(
        name="features_and_stories",
        description="Draft one feature with its user stories from a brief, review it with fresh-context reviewers, "
        "and return it for the user to save. Writes nothing outside the user's own artifacts.",
        input_schema=FeaturesIn,
        edges=[
            *with_scope(kit, p, FeaturesIn, prompt_n, end),
            (
                prompt_n,
                drafter,
                _node(to_review, f"{p}_to_review"),
                review_workflow(kit, p, "features-and-stories"),
                _node(finish, f"{p}_finish"),
            ),
        ],
    )


def design_specification(kit: Kit) -> Workflow:
    p = "design"
    key = f"sdlc_wf:{p}:source"

    async def source(ctx: Context, node_input: Any):
        """The feature to design from: the user's own (no check), or a published one (approved on the team's
        control repository and recorded in Jira)."""
        found: dict[str, Any] = {
            "control_id": node_input.get("control_id") or "",
            "jira_key": node_input.get("jira_key") or "",
        }
        try:
            if found["jira_key"]:
                status = await kit.caller.call(
                    ctx, "control_status", {"jira_key": found["jira_key"], "include_content": True}
                )
                if not status["artifacts"]["feature"]["approved"] or not status.get("jira_feature_recorded"):
                    return _stop(
                        ctx,
                        f"{found['jira_key']} is not an approved feature on the team's control repository",
                        "not_approved",
                    )
                issue = await kit.caller.call(ctx, "jira_get_issue", {"key": found["jira_key"]})
                stories = "\n".join(f"- {s['key']}: {s.get('summary', '')}" for s in issue.get("stories") or [])
                feature = (
                    status["artifacts"]["feature"].get("content", "") + f"\n\n# Jira\n\n{found['jira_key']}\n{stories}"
                )
                found["control_id"] = status["control_id"]
            elif found["control_id"]:
                status = await kit.caller.call(
                    ctx, "control_status", {"control_id": found["control_id"], "include_content": True}
                )
                if not status["artifacts"]["feature"]["approved"]:
                    return _stop(
                        ctx, f"{found['control_id']} is not approved on the team's control repository", "not_approved"
                    )
                feature = status["artifacts"]["feature"].get("content", "")
            elif (node_input.get("feature") or "").strip():
                feature = node_input["feature"]
            else:
                return _stop(
                    ctx, "name the feature: the user's own feature artifact, a Jira key or a control ID", "no_feature"
                )
        except StepError as exc:
            return _stop(ctx, exc.message or exc.code, exc.code)
        repos = node_input.get("repositories") or [
            r["repo"] for r in (node_input.get("systems") or {}).get("repositories") or [] if r.get("default")
        ]
        found |= {"feature": feature, "repositories": repos}
        ctx.state[key] = found
        ctx.route = "go"
        return (
            f"Team: {node_input['team']}\nTarget repositories: {', '.join(repos) or '(none declared)'}\n"
            f"{('Notes: ' + node_input['notes']) if node_input.get('notes') else ''}\n\n"
            f"# Feature and stories\n\n{feature}"
        )

    drafter = LlmAgent(
        name=f"{p}_drafter",
        model=kit.model(),
        mode="single_turn",
        instruction=kit.skill("design-specification") + DRAFT_RULES,
        tools=[kit.toolset(READ_TOOLS)],
    )

    async def to_review(ctx: Context, node_input: Any):
        return {"document": _strip(node_input), "context": ctx.state[key]["feature"]}

    async def finish(ctx: Context, node_input: Any):
        found = ctx.state[key]
        return {
            "status": "drafted",
            "team": ctx.state.get(TEAM_KEY),
            "control_id": found["control_id"],
            "jira_key": found["jira_key"],
            "repositories": found["repositories"],
            **node_input,
            "next": "Save the design with artifact_save and show it. It stays the user's own; when the user asks to "
            "hand it to implementation, call hand_off_design.",
        }

    source_n, end = _node(source, f"{p}_source"), _end(f"{p}_end")
    return Workflow(
        name="design_specification",
        description="Draft a design specification from the user's own feature artifact, or from a feature published "
        "on the team's control repository (by Jira key or control ID), review it with fresh-context reviewers, and "
        "return it for the user to save. Writes nothing outside the user's own artifacts.",
        input_schema=DesignIn,
        edges=[
            *with_scope(kit, p, DesignIn, source_n, end),
            (source_n, {"go": drafter, "stop": end}),
            (
                drafter,
                _node(to_review, f"{p}_to_review"),
                review_workflow(kit, p, "design-specification"),
                _node(finish, f"{p}_finish"),
            ),
        ],
    )


# Publishing workflows: control repository, merge, then the write --------------------------------------------


def merge_gate(kit: Kit, p: str, kind: str):
    """wait -> check: asks the user to have the pull request merged, then checks the approval with user_agent_mcp;
    not approved yet goes back to waiting, 'cancel' stops."""
    key = f"sdlc_wf:{p}:published"

    async def wait(ctx: Context, node_input: Any):
        published = ctx.state[key]
        reason = node_input.get("reason") if isinstance(node_input, dict) else None
        message = (
            f"I opened {published['pull_request']['url']} on your team's control repository "
            f"({published['control_id']}). "
            "Once a person has merged it, reply 'merged'; reply 'cancel' to stop here."
        )
        if reason:
            message = f"Not approved yet: {reason}. " + message
        yield RequestInput(message=message, payload={"kind": "merge_wait", **published})

    async def check(ctx: Context, node_input: Any):
        if _answer(node_input).strip().lower().startswith("cancel"):
            return _stop(ctx, "the user stopped before the merge; the pull request stays open", "cancelled")
        published = ctx.state[key]
        try:
            status = await kit.caller.call(ctx, "control_status", {"control_id": published["control_id"]})
        except StepError as exc:
            return _stop(ctx, exc.message or exc.code, exc.code)
        found = status["artifacts"][kind]
        if not found["approved"]:
            ctx.route = "wait"
            return {"reason": found.get("reason") or "the pull request is not merged"}
        ctx.state[f"{key}:approval"] = found
        ctx.state[f"{key}:writes"] = status.get("writes") or []
        ctx.route = "approved"
        return found

    return _node(wait, f"{p}_wait_for_merge"), _node(check, f"{p}_check_approval")


def publish_feature(kit: Kit) -> Workflow:
    p = "publish_feature"
    key = f"sdlc_wf:{p}:published"

    async def publish(ctx: Context, node_input: Any):
        try:
            out = await kit.caller.call(
                ctx,
                "control_publish",
                {
                    "kind": "feature",
                    "content": node_input["content"],
                    "summary": node_input["summary"],
                    "description": node_input.get("description") or "",
                },
            )
        except StepError as exc:
            return _stop(ctx, exc.message or exc.code, exc.code)
        ctx.state[key] = {"control_id": out["control_id"], "pull_request": out["pull_request"], "input": node_input}
        ctx.route = "go"
        return out

    wait, check = merge_gate(kit, p, "feature")

    async def create(ctx: Context, node_input: Any):
        published = ctx.state[key]
        data = published["input"]
        args = {"control_id": published["control_id"], "feature": data["feature"], "stories": data["stories"]}
        if data.get("project"):
            args["project"] = data["project"]
        try:
            made = await kit.caller.call(ctx, "jira_create_feature", args)
        except StepError as exc:
            return _stop(ctx, exc.message or exc.code, exc.code)
        ctx.route = "done"
        return {"status": "done", "approved_by": node_input.get("merged_by"), **made}

    publish_n, end = _node(publish, f"{p}_publish"), _end(f"{p}_end")
    create_n = _node(create, f"{p}_create_in_jira")
    return Workflow(
        name="publish_feature",
        description="Only when the user asks to add a reviewed feature and its stories to Jira: opens a pull request "
        "with it on the team's control repository, waits until a person has merged it, then creates the Feature and "
        "User Story issues as the user and records the keys on the control repository.",
        input_schema=PublishFeatureIn,
        edges=[
            *with_scope(kit, p, PublishFeatureIn, publish_n, end),
            (publish_n, {"go": wait, "stop": end}),
            (wait, check),
            (check, {"approved": create_n, "wait": wait, "stop": end}),
            (create_n, {"done": end, "stop": end}),
        ],
    )


def hand_off_design(kit: Kit) -> Workflow:
    p = "hand_off_design"
    key = f"sdlc_wf:{p}:published"

    async def publish(ctx: Context, node_input: Any):
        args = {
            "kind": "design",
            "content": node_input["content"],
            "description": node_input.get("description") or "",
            "jira_keys": node_input.get("jira_keys") or [],
        }
        if node_input.get("control_id"):
            args["control_id"] = node_input["control_id"]
        elif (node_input.get("feature") or "").strip():
            args |= {"feature": node_input["feature"], "summary": node_input.get("summary") or ""}
        else:
            return _stop(
                ctx, "a design needs its feature: a published control ID or the feature's Markdown", "no_feature"
            )
        try:
            out = await kit.caller.call(ctx, "control_publish", args)
        except StepError as exc:
            return _stop(ctx, exc.message or exc.code, exc.code)
        ctx.state[key] = {"control_id": out["control_id"], "pull_request": out["pull_request"]}
        ctx.route = "go"
        return out

    wait, check = merge_gate(kit, p, "design")

    async def link(ctx: Context, node_input: Any):
        published = ctx.state[key]
        writes = ctx.state.get(f"{key}:writes") or []
        linked = None
        if any(w.get("action") == "create_feature" for w in writes):
            try:
                linked = (await kit.caller.call(ctx, "jira_link_design", {"control_id": published["control_id"]}))[
                    "feature"
                ]
            except StepError as exc:
                return _stop(ctx, f"approved, but the Jira link failed: {exc.message or exc.code}", exc.code)
        ctx.route = "done"
        return {
            "status": "handed_off",
            "control_id": published["control_id"],
            "approved_by": node_input.get("merged_by"),
            "jira_feature_linked": linked,
            "next": "The merge on the control repository hands the design to ci_workflow_agent.",
        }

    publish_n, end = _node(publish, f"{p}_publish"), _end(f"{p}_end")
    link_n = _node(link, f"{p}_link_in_jira")
    return Workflow(
        name="hand_off_design",
        description="Only when the user asks to hand a reviewed design specification to implementation: opens a pull "
        "request with it on the team's control repository, waits until a person has merged it (the approval and "
        "hand-off), and links it to the Jira feature when there is one.",
        input_schema=HandOffIn,
        edges=[
            *with_scope(kit, p, HandOffIn, publish_n, end),
            (publish_n, {"go": wait, "stop": end}),
            (wait, check),
            (check, {"approved": link_n, "wait": wait, "stop": end}),
            (link_n, {"done": end, "stop": end}),
        ],
    )


def build_workflows(kit: Kit) -> list[Workflow]:
    return [features_and_stories(kit), design_specification(kit), publish_feature(kit), hand_off_design(kit)]
