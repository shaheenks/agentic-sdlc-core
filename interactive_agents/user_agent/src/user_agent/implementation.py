"""The implementation plan and the implementation, with the user (DEC-0016, FR-SDLC-006).

Stages after `hand_off_design`, like the others: drafts stay the user's own until the user asks for a pull request,
and every approval is a person's merge, checked by user_agent_mcp.

- `implementation_plan`: for one target repository, from the design a person merged and its stories, drafts
  `plan-<repo>.md` with the implementation-plan skill and runs the fresh-context review loop with the readiness
  reviewer. The plan is returned for the user to save.
- `hand_off_plan`: only when the user asks. Opens the plan as a pull request into the feature branch on the control
  repository (plan_publish), waits until a person has merged it, and checks the approval.
- `implementation`: from a plan a person merged, the implementer writes the change with tests and builds it in the
  Code Workspace (workspace_build), fixing failures. The user sees the change, the build and any departures from the
  plan, and may ask for another round. The built change set is saved as the user's artifact
  `implementation-<control-id>-<repo>.json`.
- `open_implementation`: only when the user asks. Commits that change set to `sdlc/<control-id>/<repo>` and opens
  its pull request into the target repository's feature branch (implementation_publish), as the user.
"""

import json
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.events import RequestInput
from google.adk.workflow import Workflow
from pydantic import BaseModel, Field

from user_agent.identity import TEAM_KEY
from user_agent.mcp_client import StepError
from user_agent.workflows import (
    DRAFT_RULES,
    READ_TOOLS,
    Kit,
    _answer,
    _end,
    _node,
    _stop,
    _strip,
    merge_gate,
    reading_budget,
    review_workflow,
    with_scope,
)

PLAN_REVIEWERS = ("review-readiness",)  # DEC-0016: one fresh-context reviewer for a plan
BUILD_TOOL = "workspace_build"
IMPLEMENT_READS = {"repo_read_file": 30, "repo_list": 10}
MAX_BUILDS_PER_ROUND = 5
SHOWN_FILES = 40


class PlanIn(BaseModel):
    team: str
    control_id: str = Field(description="The feature's control ID; its design must be merged.")
    repo: str = Field("", description="The target repository (owner/name); the feature's first target if empty.")
    notes: str = ""


class HandOffPlanIn(BaseModel):
    team: str
    control_id: str
    repo: str = Field(description="The target repository the plan is for (owner/name).")
    content: str = Field(description="The plan as reviewed (Markdown).")
    description: str = ""


class ImplementIn(BaseModel):
    team: str
    control_id: str = Field(description="The feature's control ID; the repository's plan must be merged.")
    repo: str = Field(description="The target repository (owner/name).")
    notes: str = ""


class OpenImplementationIn(BaseModel):
    team: str
    control_id: str
    repo: str
    title: str = ""
    description: str = ""


def artifact_name(control_id: str, repo: str) -> str:
    return f"implementation-{control_id}-{repo.rsplit('/', 1)[-1]}.json"


def _pick_repo(status: dict[str, Any], wanted: str) -> str | None:
    targets = list(status.get("plans") or {}) or list(status.get("target_repositories") or [])
    if not wanted:
        return targets[0] if targets else None
    return next((r for r in targets if wanted.lower() in (r.lower(), r.rsplit("/", 1)[-1].lower())), None)


# The plan -------------------------------------------------------------------------------------------------------

PLAN_RULES = """

In this workflow the merged design, the feature and its stories (with their Jira keys) are in the message: you do not
need control_read_file. Read the repository's code with repo_list and repo_read_file at the feature branch named in
the message."""


def implementation_plan(kit: Kit) -> Workflow:
    p = "plan"
    key, reads = f"sdlc_wf:{p}:source", f"sdlc_wf:{p}:reads"

    async def source(ctx: Context, node_input: Any):
        control_id = node_input["control_id"]
        try:
            status = await kit.caller.call(ctx, "control_status", {"control_id": control_id, "include_content": True})
        except StepError as exc:
            return _stop(ctx, exc.message or exc.code, exc.code)
        design = status["artifacts"]["design"]
        if not design.get("approved"):
            reason = design.get("reason") or "the design is not merged"
            return _stop(ctx, f"{control_id}'s design is not approved: {reason}. Hand it off first.", "not_approved")
        repo = _pick_repo(status, node_input.get("repo") or "")
        if repo is None:
            return _stop(
                ctx, f"{node_input.get('repo') or 'no repository'} is not one of the feature's targets", "not_found"
            )
        if ((status.get("plans") or {}).get(repo) or {}).get("approved"):
            return _stop(ctx, f"the plan for {repo} is approved already: implement it", "already_done")
        ctx.state[key] = {"control_id": control_id, "repo": repo, "design": design.get("content", "")}
        ctx.state[reads] = {}
        ctx.route = "go"
        keys = ", ".join(status.get("jira_keys") or []) or "-"
        return (
            f"Team: {node_input['team']}\nTarget repository: {repo}\nRead it at ref: {status.get('branch')}\n"
            f"Control ID: {control_id}\nJira keys: {keys}\n"
            f"{('Notes: ' + node_input['notes']) if node_input.get('notes') else ''}\n\n"
            f"# Feature and stories\n\n{status['artifacts']['feature'].get('content', '')}\n\n"
            f"# Design\n\n{design.get('content', '')}"
        )

    drafter = LlmAgent(
        name=f"{p}_drafter",
        model=kit.model(),
        mode="single_turn",
        instruction=kit.skill("implementation-plan") + PLAN_RULES + DRAFT_RULES,
        tools=[kit.toolset(READ_TOOLS)],
        before_tool_callback=reading_budget(reads),
    )

    async def to_review(ctx: Context, node_input: Any):
        return {"document": _strip(node_input), "context": ctx.state[key]["design"]}

    async def finish(ctx: Context, node_input: Any):
        found = ctx.state[key]
        return {
            "status": "drafted",
            "team": ctx.state.get(TEAM_KEY),
            "control_id": found["control_id"],
            "repo": found["repo"],
            **node_input,
            "next": "Save the plan with artifact_save and show it. It stays the user's own; when the user asks to "
            "propose it, call hand_off_plan.",
        }

    source_n, end = _node(source, f"{p}_source"), _end(f"{p}_end")
    return Workflow(
        name="implementation_plan",
        description="Draft the implementation plan for one target repository from a feature's merged design and its "
        "stories, review it with a fresh-context reviewer, and return it for the user to save. Writes nothing outside "
        "the user's own artifacts.",
        input_schema=PlanIn,
        edges=[
            *with_scope(kit, p, PlanIn, source_n, end),
            (source_n, {"go": drafter, "stop": end}),
            (
                drafter,
                _node(to_review, f"{p}_to_review"),
                review_workflow(kit, p, "implementation-plan", PLAN_REVIEWERS),
                _node(finish, f"{p}_finish"),
            ),
        ],
    )


def hand_off_plan(kit: Kit) -> Workflow:
    p = "hand_off_plan"
    key = f"sdlc_wf:{p}:published"

    async def publish(ctx: Context, node_input: Any):
        args = {
            "control_id": node_input["control_id"],
            "repo": node_input["repo"],
            "content": node_input["content"],
            "description": node_input.get("description") or "",
        }
        try:
            out = await kit.caller.call(ctx, "plan_publish", args)
        except StepError as exc:
            return _stop(ctx, exc.message or exc.code, exc.code)
        ctx.state[key] = {
            "control_id": out["control_id"],
            "repo": out.get("repo") or node_input["repo"],
            "pull_request": out["pull_request"],
            "already_open": bool(out.get("already_open")),
        }
        ctx.route = "go"
        return out

    def plan_of(ctx: Context, status: dict[str, Any]) -> dict[str, Any]:
        repo = ctx.state[key]["repo"]
        return (status.get("plans") or {}).get(repo) or {"approved": False, "reason": "the plan is not merged"}

    wait, check = merge_gate(kit, p, "plan", plan_of)

    async def done(ctx: Context, node_input: Any):
        published = ctx.state[key]
        ctx.route = "done"
        return {
            "status": "approved",
            "control_id": published["control_id"],
            "repo": published["repo"],
            "approved_by": node_input.get("merged_by"),
            "next": "The plan is approved. When the user wants it implemented, call implementation.",
        }

    publish_n, end = _node(publish, f"{p}_publish"), _end(f"{p}_end")
    done_n = _node(done, f"{p}_approved")
    return Workflow(
        name="hand_off_plan",
        description="Only when the user asks to propose a reviewed implementation plan: opens it as a pull request "
        "into the feature branch on the team's control repository, as the user, and waits until a person has merged "
        "it (the approval).",
        input_schema=HandOffPlanIn,
        edges=[
            *with_scope(kit, p, HandOffPlanIn, publish_n, end),
            (publish_n, {"go": wait, "stop": end}),
            (wait, check),
            (check, {"approved": done_n, "wait": wait, "stop": end}),
            (done_n, {"done": end}),
        ],
    )


# The implementation ---------------------------------------------------------------------------------------------

IMPLEMENT_RULES = f"""

In this workflow you work for the user, who will see your result and may ask for another round; you cannot ask
them anything until you finish. The approved plan and the design are in the message: you do not need
control_read_file. Read the code with repo_list and repo_read_file at the ref the message names.
The build tool here is {BUILD_TOOL}, not workspace_run, and it pushes nothing: every {BUILD_TOOL} call carries the
complete change set (every file you create, change or delete, compared with the ref), not only the files that
changed since the last call. Build at most {MAX_BUILDS_PER_ROUND} times. End with the JSON your instructions describe;
`ready` means the last {BUILD_TOOL} call passed (or the repository declares no commands)."""


def _response_payload(response: Any) -> dict[str, Any]:
    """The tool's JSON answer, from an MCP tool response or a plain dict."""
    if isinstance(response, dict):
        if "ok" in response or "error" in response:
            return response
        for part in response.get("content") or []:
            text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
            try:
                found = json.loads(text or "")
            except (TypeError, ValueError):
                continue
            if isinstance(found, dict):
                return found
        structured = response.get("structuredContent") or response.get("structured_content")
        if isinstance(structured, dict):
            return structured
    return {}


def implementation(kit: Kit) -> Workflow:
    p = "implement"
    key, reads, built = f"sdlc_wf:{p}:context", f"sdlc_wf:{p}:reads", f"sdlc_wf:{p}:built"

    def limits(tool, args, tool_context):
        if getattr(tool, "name", "") == BUILD_TOOL:
            count = int(tool_context.state.get(f"{built}:count") or 0)
            if count >= MAX_BUILDS_PER_ROUND:
                return {"error": "limit_reached", "message": "the builds of this round are used up: report as you are"}
            tool_context.state[f"{built}:count"] = count + 1
            return None
        name = getattr(tool, "name", "")
        limit = IMPLEMENT_READS.get(name)
        if limit is None:
            return None
        used = dict(tool_context.state.get(reads) or {})
        if used.get(name, 0) >= limit:
            return {"error": "read_limit", "message": f"the reading budget ({limit} {name} calls) is used up"}
        used[name] = used.get(name, 0) + 1
        tool_context.state[reads] = used
        return None

    def capture(tool, args, tool_context, tool_response):
        """The change set of the last build and how it went: what the user approves and what is committed."""
        if getattr(tool, "name", "") != BUILD_TOOL:
            return None
        result = _response_payload(tool_response)
        tool_context.state[built] = {
            "changes": list((args or {}).get("changes") or []),
            "ok": bool(result.get("ok")),
            "built": bool(result.get("built", True)),
            "steps": [
                {k: s.get(k) for k in ("name", "command", "exit_code", "seconds")}
                for s in result.get("steps") or []
                if isinstance(s, dict)
            ],
            "error": result.get("error") or "",
        }
        return None

    async def source(ctx: Context, node_input: Any):
        control_id = node_input["control_id"]
        try:
            status = await kit.caller.call(ctx, "control_status", {"control_id": control_id, "include_content": True})
        except StepError as exc:
            return _stop(ctx, exc.message or exc.code, exc.code)
        repo = _pick_repo(status, node_input.get("repo") or "")
        if repo is None:
            return _stop(ctx, f"{node_input.get('repo')} is not one of {control_id}'s target repositories", "not_found")
        plan = (status.get("plans") or {}).get(repo) or {}
        if not plan.get("approved"):
            reason = plan.get("reason") or "the plan is not merged"
            return _stop(ctx, f"the plan for {repo} is not approved: {reason}. Hand it off first.", "not_approved")
        branch = f"sdlc/{control_id}/{repo.rsplit('/', 1)[-1]}"
        keys = ", ".join(status.get("jira_keys") or []) or "-"
        ctx.state[key] = {
            "control_id": control_id,
            "repo": repo,
            "prompt": (
                f"Repository: {repo}\nRead it at ref: {status.get('branch')} (or {branch} if it exists: an earlier "
                f"round's change)\nControl ID: {control_id}\nJira keys: {keys}"
                f"\n{('Notes: ' + node_input['notes']) if node_input.get('notes') else ''}\n\n"
                f"# Plan\n\n{plan.get('content', '')}\n\n# Design\n\n{status['artifacts']['design'].get('content', '')}"
            ),
        }
        ctx.state[built], ctx.state[f"{built}:count"], ctx.state[reads] = {}, 0, {}
        ctx.route = "go"
        return ctx.state[key]["prompt"]

    implementer = LlmAgent(
        name=f"{p}_implementer",
        model=kit.model(),
        mode="single_turn",
        instruction=kit.skill("implementation") + IMPLEMENT_RULES,
        tools=[kit.toolset([*READ_TOOLS, BUILD_TOOL])],
        before_tool_callback=limits,
        after_tool_callback=capture,
    )

    async def report(ctx: Context, node_input: Any):
        try:
            found = json.loads(_strip(node_input))
        except (ValueError, TypeError):
            found = {}
        found = found if isinstance(found, dict) else {}
        last = ctx.state.get(built) or {}
        ctx.state[f"{key}:report"] = found
        if found.get("status") != "ready" or not last.get("changes"):
            reason = found.get("blocked_reason") or (
                "no change was built" if not last.get("changes") else "the implementer gave no usable result"
            )
            ctx.route = "blocked"
            return {"status": "blocked", "reason": str(reason), "build": last}
        ctx.route = "show"
        return {"report": found, "build": last}

    async def show(ctx: Context, node_input: Any):
        c, build, found = ctx.state[key], node_input["build"], node_input["report"]
        files = [ch["path"] + (" (deleted)" if ch.get("delete") else "") for ch in build["changes"]][:SHOWN_FILES]
        if not build.get("built"):
            verdict = "not built here (no commands declared; CI proves it)"
        else:
            verdict = "built and tested" if build.get("ok") else "failing"
        yield RequestInput(
            message=(
                f"The change for {c['repo']} is {verdict}: {len(build['changes'])} files. Reply 'ok' to keep it "
                "(then ask me to open its pull request), or say what to change for another round."
            ),
            payload={
                "kind": "implementation_review",
                "repo": c["repo"],
                "title": found.get("title") or "",
                "summary": found.get("summary") or "",
                "departures": found.get("departures") or "",
                "files": files,
                "build": {k: build.get(k) for k in ("ok", "built", "steps", "error")},
            },
        )

    async def decide(ctx: Context, node_input: Any):
        answer = _answer(node_input).strip()
        if answer.lower() in ("ok", "yes", "keep", "keep it", "done", "looks good"):
            ctx.route = "keep"
            return None
        if answer.lower() in ("stop", "cancel", "no"):
            return _stop(ctx, "the user stopped; the change was not kept", "cancelled")
        c, build = ctx.state[key], ctx.state[built]
        current = "\n\n".join(
            f"## {ch['path']}\n\n" + ("(deleted)" if ch.get("delete") else f"```\n{ch.get('content', '')}\n```")
            for ch in build["changes"]
        )
        ctx.state[f"{built}:count"] = 0
        ctx.route = "again"
        return (
            f"{c['prompt']}\n\n# The change so far (your complete change set)\n\n{current}\n\n"
            f"# The user's changes for this round\n\n{answer}"
        )

    async def keep(ctx: Context, node_input: Any):
        c, build, found = ctx.state[key], ctx.state[built], ctx.state.get(f"{key}:report") or {}
        document = {
            "control_id": c["control_id"],
            "repo": c["repo"],
            "title": found.get("title") or "",
            "summary": found.get("summary") or "",
            "departures": found.get("departures") or "",
            "changes": build["changes"],
        }
        name = artifact_name(c["control_id"], c["repo"])
        try:
            await kit.caller.call(
                ctx,
                "artifact_save",
                {"name": name, "content": json.dumps(document), "content_type": "application/json"},
            )
        except StepError as exc:
            return _stop(ctx, f"the change could not be saved: {exc.message or exc.code}", exc.code)
        ctx.route = "done"
        return {
            "status": "built",
            "control_id": c["control_id"],
            "repo": c["repo"],
            "artifact": name,
            "files": len(build["changes"]),
            "build": {k: build.get(k) for k in ("ok", "built", "steps")},
            "title": document["title"],
            "summary": document["summary"],
            "departures": document["departures"],
            "next": "The change is saved as the user's artifact. When the user asks to open its pull request, call "
            "open_implementation.",
        }

    async def blocked(ctx: Context, node_input: Any):
        c = ctx.state[key]
        return {"status": "blocked", "control_id": c["control_id"], "repo": c["repo"], "reason": node_input["reason"]}

    source_n, end = _node(source, f"{p}_source"), _end(f"{p}_end")
    report_n, show_n, decide_n = _node(report, f"{p}_report"), _node(show, f"{p}_show"), _node(decide, f"{p}_decide")
    keep_n, blocked_n = _node(keep, f"{p}_keep"), _node(blocked, f"{p}_blocked")
    return Workflow(
        name="implementation",
        description="Implement a target repository's approved plan with tests: write the change, build and test it "
        "in the Code Workspace, show it to the user and take their changes for another round. Saves the kept change "
        "as the user's artifact; opens nothing.",
        input_schema=ImplementIn,
        edges=[
            *with_scope(kit, p, ImplementIn, source_n, end),
            (source_n, {"go": implementer, "stop": end}),
            (implementer, report_n),
            (report_n, {"show": show_n, "blocked": blocked_n}),
            (show_n, decide_n),
            (decide_n, {"keep": keep_n, "again": implementer, "stop": end}),
            (keep_n, {"done": end, "stop": end}),
            (blocked_n, end),
        ],
    )


def open_implementation(kit: Kit) -> Workflow:
    p = "open_implementation"

    async def publish(ctx: Context, node_input: Any):
        name = artifact_name(node_input["control_id"], node_input["repo"])
        try:
            saved = await kit.caller.call(ctx, "artifact_read", {"name": name})
            document = json.loads(saved.get("content") or "{}")
        except StepError as exc:
            return _stop(ctx, f"no kept change for {node_input['repo']} ({name}): {exc.message or exc.code}", exc.code)
        except ValueError:
            return _stop(ctx, f"{name} is not a change set", "invalid_argument")
        description = str(node_input.get("description") or document.get("summary") or "")
        if document.get("departures"):
            description += f"\n\n## Departures from the plan\n\n{document['departures']}"
        args = {
            "control_id": node_input["control_id"],
            "repo": document.get("repo") or node_input["repo"],
            "changes": document.get("changes") or [],
            "title": (node_input.get("title") or document.get("title") or "")[:150]
            or f"{node_input['control_id']}: implementation",
            "description": description,
        }
        try:
            out = await kit.caller.call(ctx, "implementation_publish", args)
        except StepError as exc:
            return _stop(ctx, exc.message or exc.code, exc.code)
        ctx.route = "done"
        return {
            "status": "opened" if not out.get("already_open") else "updated",
            "control_id": node_input["control_id"],
            "repo": args["repo"],
            "pull_request": out.get("pull_request"),
            "commit": out.get("commit"),
            "next": "A person reviews and merges the pull request into the feature branch; the repository's CI runs on "
            "it.",
        }

    publish_n, end = _node(publish, f"{p}_publish"), _end(f"{p}_end")
    return Workflow(
        name="open_implementation",
        description="Only when the user asks to open the pull request of a kept change (from implementation): commits "
        "it to the implementation branch and opens the pull request into the target repository's feature branch, as "
        "the user. An open one is updated with the change instead of a second.",
        input_schema=OpenImplementationIn,
        edges=[
            *with_scope(kit, p, OpenImplementationIn, publish_n, end),
            (publish_n, {"done": end, "stop": end}),
        ],
    )


def implementation_workflows(kit: Kit) -> list[Workflow]:
    return [implementation_plan(kit), hand_off_plan(kit), implementation(kit), open_implementation(kit)]
