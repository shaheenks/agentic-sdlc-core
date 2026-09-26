"""Bootstrap ADK root agent.

Stage 1: connects to the bootstrap MCP server and works through skills.
Stage 2 adds `header_provider=get_user_token(...)` so the user's Entra token is forwarded.
Authorization is never decided here; the MCP server decides what this agent can see.
"""

import os

from google.adk.agents import Agent
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

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
    instruction=INSTRUCTION,
    tools=[McpToolset(connection_params=StreamableHTTPConnectionParams(url=MCP_URL))],
)
