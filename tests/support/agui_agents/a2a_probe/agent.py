"""Test-only agent for the A2A endpoint (version-03 P4 C3): a scripted model calls `whoami` once,
then answers. `whoami` records what a tool sees (token, oid, session user, state keys) and returns
an identity, so the real A2UI card callbacks attach cards to its result. No network, no LLM."""

from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext
from sdlc_agent.a2ui_cards import after_tool_callback, before_model_callback
from sdlc_auth.adk import get_user_token
from sdlc_web.middleware import current_oid

from tests.support.agui_agents.probe.agent import ScriptedModel
from tests.support.agui_records import RECORDS


class WhoamiModel(ScriptedModel):
    async def generate_content_async(self, llm_request, stream: bool = False):
        RECORDS.append({"model_saw": str(llm_request.contents)})
        async for response in super().generate_content_async(llm_request, stream):
            part = response.content.parts[0]
            if part.function_call is not None:
                part.function_call.name = "whoami"
            yield response


def whoami(tool_context: ToolContext) -> dict:
    """Record the identity a tool sees; answer like the MCP whoami tool."""
    try:
        oid = current_oid()
    except PermissionError:
        oid = None
    RECORDS.append(
        {
            "token": get_user_token(tool_context),
            "oid": oid,
            "session_user": tool_context.session.user_id,
            "session_id": tool_context.session.id,
            "state_keys": sorted(tool_context.state.to_dict()),
        }
    )
    return {"oid": oid, "name": "Probe User", "groups": ["eng-all"]}


root_agent = Agent(
    name="a2a_probe",
    model=WhoamiModel(model="scripted"),
    tools=[whoami],
    after_tool_callback=after_tool_callback,
    before_model_callback=before_model_callback,
)
