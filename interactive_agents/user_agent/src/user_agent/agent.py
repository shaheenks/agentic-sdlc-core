"""user_agent: ad-hoc knowledge search and brainstorming for the signed-in user (FR-AGT-005).

Every tool is a user_agent_mcp tool, listed and allowed for this user and surface by user_agent_mcp itself; the
agent holds no credential of its own beyond proving it is the runtime (DEC-0010)."""

import os

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from user_agent.identity import TITLE_KEY, header_provider, tokens_from_env

DEFAULT_MODEL = "gemini-3.8-flash"
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
- Keep answers short unless the user asks for depth."""


def model() -> Gemini:
    from google.genai import Client

    client = Client(
        vertexai=True,
        project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        location=os.environ.get("SDLC_MODEL_LOCATION", DEFAULT_MODEL_LOCATION),
    )
    return Gemini(model=os.environ.get("SDLC_AGENT_MODEL", DEFAULT_MODEL), client=client)


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
    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=mcp_url, timeout=float(os.environ.get("SDLC_MCP_TIMEOUT", "30"))
        ),
        header_provider=header_provider(tokens_from_env(mcp_url)),
    )
    return Agent(
        name="user_agent",
        model=model(),
        instruction=INSTRUCTION,
        tools=[toolset],
        before_agent_callback=title_from_first_message,
    )
