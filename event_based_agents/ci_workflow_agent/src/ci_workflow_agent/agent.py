"""ci_workflow_agent's root: the plan and implement workflows (DEC-0015), with event_agent_mcp's tools.

Every tool is an event_agent_mcp tool, allowed for the system identity and the run's subscription by the server; the
agent holds no credential of its own beyond proving it is the runtime."""

import os
from pathlib import Path

from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from sdlc_adk import McpCaller, gemini, load_skills, skills_dir

from ci_workflow_agent.identity import header_provider, mcp_headers, tokens_from_env
from ci_workflow_agent.workflows import Kit, build_root

DEFAULT_MODEL = "gemini-3.8-flash"
DEFAULT_REVIEW_MODEL = "gemini-3.5-flash"
DEFAULT_MODEL_LOCATION = "eu"  # served there for the runtime in europe-west3 (NFR-HOST-005)
HERE = Path(__file__).resolve()
PACKAGED = HERE.parent / "skills"
REPOSITORY = HERE.parents[4] / "skills" if len(HERE.parents) > 4 else None


def skill(name: str) -> str:
    return load_skills(skills_dir((os.environ.get("SDLC_SKILLS_DIR"), PACKAGED, REPOSITORY)))[name]


def model(name: str | None = None):
    return gemini(
        name or os.environ.get("SDLC_AGENT_MODEL", DEFAULT_MODEL),
        os.environ.get("SDLC_MODEL_LOCATION", DEFAULT_MODEL_LOCATION),
    )


def review_model():
    return model(os.environ.get("SDLC_REVIEW_MODEL", DEFAULT_REVIEW_MODEL))


def build_agent():
    mcp_url = os.environ.get("SDLC_MCP_URL", "http://127.0.0.1:8081/mcp")
    timeout = float(os.environ.get("SDLC_MCP_TIMEOUT", "60"))
    tokens = tokens_from_env(mcp_url)

    def tools(only: list[str] | None = None) -> McpToolset:
        return McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=mcp_url, timeout=timeout),
            header_provider=header_provider(tokens),
            tool_filter=only,
        )

    caller = McpCaller(mcp_url, lambda ctx: mcp_headers(ctx.state, tokens), timeout, client_name="ci_workflow_agent")
    return build_root(Kit(model=model, caller=caller, toolset=tools, skill=skill, review_model=review_model))
