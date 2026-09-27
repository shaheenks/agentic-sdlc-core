"""Bootstrap ADK root agent.

Stage 1: connects to the bootstrap MCP server and works through skills.
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
from sdlc_auth.adk import bearer_header_provider

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
"""

root_agent = Agent(
    name="sdlc_bootstrap",
    model=MODEL,
    description="Starter SDLC assistant that works through centrally served skills.",
    instruction=with_team_context(INSTRUCTION, MCP_URL),
    tools=[
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=MCP_URL),
            header_provider=bearer_header_provider,
        )
    ],
)
