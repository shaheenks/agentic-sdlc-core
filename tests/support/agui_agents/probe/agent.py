"""Test-only agent for the AG-UI spike (version-01 M5): a scripted model calls `probe` once, then
answers. `probe` records what a tool sees during a real /agui run: the user token
(sdlc_auth.adk.get_user_token), the bound oid, and the session's user id and state keys."""

from collections.abc import AsyncGenerator

from google.adk.agents import Agent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from sdlc_auth.adk import get_user_token
from sdlc_web.middleware import current_oid

from tests.support.agui_records import RECORDS


class ScriptedModel(BaseLlm):
    """First turn: call the probe tool. After its result: answer with text. No network."""

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        last = llm_request.contents[-1] if llm_request.contents else None
        answered = last is not None and any(p.function_response for p in last.parts or [])
        if answered:
            part = types.Part(text="probe done")
        else:
            part = types.Part(function_call=types.FunctionCall(name="probe", args={}))
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


def probe(tool_context: ToolContext) -> dict:
    """Record the identity a tool sees."""
    try:
        oid = current_oid()
    except PermissionError:
        oid = None
    RECORDS.append(
        {
            "token": get_user_token(tool_context),
            "oid": oid,
            "session_user": tool_context.session.user_id,
            "state_keys": sorted(tool_context.state.to_dict()),
        }
    )
    return {"ok": True}


root_agent = Agent(name="probe", model=ScriptedModel(model="scripted"), tools=[probe])
