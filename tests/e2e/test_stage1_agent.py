"""Stage 1 exit gate: the agent lists skills and follows one end-to-end.

Needs a running MCP server (`docker compose up`) and Gemini credentials in the environment
(GOOGLE_API_KEY, or GOOGLE_GENAI_USE_VERTEXAI=TRUE + project). Skipped otherwise.
Run: uv run --env-file .env pytest tests/e2e -m e2e
"""

import os
import sys
import urllib.request
from pathlib import Path

import pytest
from google.genai import types

pytestmark = pytest.mark.e2e

MCP_URL = os.environ.get("SDLC_MCP_URL", "http://127.0.0.1:8080/mcp")
HEALTH_URL = MCP_URL.rsplit("/", 1)[0] + "/healthz"
AGENTS_DIR = str(Path(__file__).resolve().parents[2] / "agents")


def _mcp_up() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=2):  # noqa: S310 (local URL)
            return True
    except OSError:
        return False


def _has_gemini_credentials() -> bool:
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE":
        return bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    return bool(os.environ.get("GOOGLE_API_KEY"))


@pytest.mark.skipif(not _has_gemini_credentials(), reason="no Gemini credentials")
@pytest.mark.skipif(not _mcp_up(), reason=f"MCP server not reachable at {HEALTH_URL}")
async def test_agent_uses_skill_end_to_end():
    from google.adk.runners import InMemoryRunner

    sys.path.insert(0, AGENTS_DIR)
    from bootstrap.agent import root_agent

    runner = InMemoryRunner(agent=root_agent, app_name="bootstrap")
    session = await runner.session_service.create_session(app_name="bootstrap", user_id="e2e")
    prompt = (
        "Write a user story: finance analysts need to export monthly invoices to CSV "
        "so they can reconcile them in their spreadsheet tool."
    )
    calls: list[str] = []
    final_text = ""
    try:
        async for event in runner.run_async(
            user_id="e2e",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
        ):
            calls += [c.name for c in event.get_function_calls()]
            if event.is_final_response() and event.content and event.content.parts:
                final_text += "".join(p.text or "" for p in event.content.parts)
    finally:
        await runner.close()

    assert "list_skills" in calls
    assert "load_skill" in calls
    assert "As a" in final_text and "Given" in final_text
