"""user_agent: knowledge search, brainstorming and the SDLC workflows for the signed-in user (FR-AGT-005,
FR-SDLC-002 to FR-SDLC-005).

Every tool is a user_agent_mcp tool, listed and allowed for this user and surface by user_agent_mcp itself; the
agent holds no credential of its own beyond proving it is the runtime (DEC-0010)."""

import os

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from sdlc_adk import gemini

from user_agent.identity import TITLE_KEY, header_provider, tokens_from_env
from user_agent.mcp_client import McpCaller
from user_agent.skills import skill
from user_agent.workflows import Kit, build_workflows

DEFAULT_MODEL = "gemini-3.8-flash"
# The seven reviewers per round use a faster model: their output is a short JSON list (2026-11-25, the user's choice).
DEFAULT_REVIEW_MODEL = "gemini-3.5-flash"
# The runtime runs in europe-west3; this model is served in `eu` (NFR-HOST-005).
DEFAULT_MODEL_LOCATION = "eu"
INSTRUCTION = """You are user_agent, the assistant of an internal software delivery platform. You help the
signed-in user find things out from the knowledge they may read, and think problems through with them.

- For questions about systems, requirements, decisions, designs or code, search first: use knowledge_search
  (hybrid by default; keyword for exact names or IDs such as FR-AUTHZ-004) and knowledge_graph to explore how
  things relate. One to three searches are usually enough; stop searching once you can answer.
- Answer from what you found. Cite each fact with its source as a Markdown link, [path](link). If the
  knowledge you can read does not answer the question, say so; never invent a source.
- You see only the sources this user may read. Do not speculate about what else exists.
- When brainstorming, be concrete: options, trade-offs, open questions. Offer to save a result as an artifact
  (artifact_save) and save it only when the user agrees.
- Keep answers short unless the user asks for depth.

Workflows (your tools of the same names). Each works for one of the user's teams and passes it as `team`. A chat
started for a team has it already (whoami shows it as access.team): use that one. Otherwise ask which of the user's
teams (whoami lists them) it is for.
- features_and_stories: when the user wants a feature and user stories. First make sure the problem, users, scope,
  constraints, success measure and open questions are clear (brainstorm with them; the brainstorm skill's
  questions), then pass the brief.
- design_specification: when the user wants a design. Pass the user's own feature artifact (read it with
  artifact_read), or the Jira key or control ID of a published feature.
- Both return a reviewed draft. Save it with artifact_save (text/markdown) and show it. It stays the user's own: the
  user can keep working on it or go on to the next step with it, and nothing is written anywhere else.
- publish_feature: when the user wants the feature and stories in Jira. Pass the reviewed Markdown and the feature
  and stories as items (summary, description with the acceptance criteria, the feature's estimate XS-XL with its
  note, each story's points), the epic from the draft's Jira section (an open epic's key, or the proposed epic's
  summary and description), and the target repositories. It shows the user the open epics and asks them to approve
  the feature and choose its epic; on approval it opens the feature branch on the control and target repositories
  and creates the Epic, Feature and User Stories (sub-tasks) as the user, reusing open issues.
- hand_off_design: only when the user asks to hand a design to implementation. It needs the feature's control_id:
  the design goes as a pull request into the feature branch, and a person merging it approves it.
- Never call feature_open, jira_create_feature, control_publish or jira_link_design yourself; the workflows do.
- Before any pull request is raised, check for a similar one: list the open pull requests (control_pull_requests on
  the team's control repository, repo_pull_requests on a target repository) and tell the user about any for the same
  feature or change, with its link; ask whether to continue with it instead. The workflows never open a second pull
  request for the same artifact: they wait on the open one.
- If publish_feature stops after the feature was approved (for example Jira rejected the issues), never start it
  again without its control_id: explain the reason to the user, and once it is fixed call publish_feature with the
  control_id it returned (and the same epic); nothing is opened or created twice. Likewise when the user points to
  a feature already approved: pass its control_id.
- When a workflow asks the user something (review findings, a team change, approving a feature and its epic,
  waiting for a merge), the chat shows it as a card; pass on its question plainly and send back the user's answer."""


def model(name: str | None = None) -> Gemini:
    """Gemini on Vertex AI, retrying the model's transient refusals (sdlc_adk.gemini)."""
    return gemini(
        name or os.environ.get("SDLC_AGENT_MODEL", DEFAULT_MODEL),
        os.environ.get("SDLC_MODEL_LOCATION", DEFAULT_MODEL_LOCATION),
    )


def review_model() -> Gemini:
    return model(os.environ.get("SDLC_REVIEW_MODEL", DEFAULT_REVIEW_MODEL))


TITLE_CHARS = 80


def title_from_first_message(callback_context) -> None:
    """The chat's title, for the list of past chats: its first message, written once by the agent."""
    if callback_context.state.get(TITLE_KEY):
        return None
    content = callback_context.user_content
    text = " ".join(p.text for p in (content.parts if content else []) or [] if getattr(p, "text", None)).strip()
    if text:
        title = " ".join(text.split())
        callback_context.state[TITLE_KEY] = title if len(title) <= TITLE_CHARS else title[: TITLE_CHARS - 1] + "…"
    return None


def build_agent() -> Agent:
    mcp_url = os.environ.get("SDLC_MCP_URL", "http://127.0.0.1:8080/mcp")
    timeout = float(os.environ.get("SDLC_MCP_TIMEOUT", "30"))
    tokens = tokens_from_env(mcp_url)

    def tools(only: list[str] | None = None) -> McpToolset:
        return McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=mcp_url, timeout=timeout),
            header_provider=header_provider(tokens),
            tool_filter=only,
        )

    # Drafting and reviewing agents get read-only tools; the workflows' own steps call user_agent_mcp directly.
    kit = Kit(
        model=model,
        caller=McpCaller(mcp_url, tokens, timeout),
        toolset=tools,
        skill=skill,
        review_model=review_model,
    )
    toolset = tools()
    return Agent(
        name="user_agent",
        model=model(),
        instruction=INSTRUCTION,
        tools=[toolset, *build_workflows(kit)],
        before_agent_callback=title_from_first_message,
    )
