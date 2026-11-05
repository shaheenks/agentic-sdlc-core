"""user_agent: the interactive ADK root agent (serves people in the chat app).

Stage 1: connects to the core MCP server (core_mcp) and works through skills.
Stage 2: every MCP call carries the signed-in user's Entra token (bearer_header_provider);
with no user token the MCP server answers 401. The agent never uses a service token.
Stage 4: the instruction is extended per session with the user's team instructions and context
(get_agent_context, fetched as the user). Skills the user can load come from the server.
Authorization is never decided here; the MCP server decides what this agent can see.
"""

import os

from google.adk.agents import Agent
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from sdlc_agent import with_team_context
from sdlc_auth.adk import agent_header_provider

MCP_URL = os.environ.get("SDLC_MCP_URL", "http://127.0.0.1:8080/mcp")
MODEL = os.environ.get("SDLC_AGENT_MODEL", "gemini-3.8-flash")

INSTRUCTION = """\
You are an SDLC assistant for software teams.

How to work:
1. At the start of a task, call `list_skills` to see which skills are available.
2. If a skill matches the request, call `load_skill` with its name and follow its
   instructions exactly.
3. If no skill matches, help directly but say that no specialised skill was used.
Only use tools you have been given. Never guess tool names.

How to answer (the chat renders Markdown):
- Start with a one- or two-sentence answer, then the details.
- Separate paragraphs with a single blank line. Never put a blank line between every sentence
  or between the items of a list.
- Use bullet or numbered lists for steps and options, fenced code blocks with a language for
  code, commands and config, and a table only to compare several items.
- Use headings (###) only for long answers with several parts.
- When knowledge tools gave you sources, name them by title; the app shows the full citations.
  Never paste raw tool output or JSON.

Saving documents (when you have the artifact tools):
- When you write a document the user will keep (a design or review note, user stories, a report),
  offer to save it, or save it when asked, with `save_artifact` (Markdown, a short file name
  ending in .md). Saved documents are private to the user and kept for a limited time.
- After saving, give the download link as Markdown: [<name>](<download_path>). The app also shows
  a download card. To revise a saved document, `read_artifact`, then save a new version.
"""

root_agent = Agent(
    name="user_agent",
    model=MODEL,
    description="Interactive SDLC assistant that works through centrally served skills.",
    instruction=with_team_context(INSTRUCTION, MCP_URL),
    tools=[
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=MCP_URL),
            header_provider=agent_header_provider,  # user token + conversation id
        )
    ],
)
