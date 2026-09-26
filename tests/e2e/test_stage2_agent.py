"""Stage 2 end-to-end check: a signed-in user's agent run reaches the MCP server as that user.

Full path, in-process except the MCP server:
  real Entra user token -> sdlc_web middleware (validates against Entra JWKS, binds user)
  -> ADK /run -> agent -> Gemini -> McpToolset with bearer_header_provider
  -> MCP server (docker, validates the same token) -> list_skills / load_skill.

Needs: `docker compose up` (MCP server with the real Entra config), Gemini credentials, and a
test user's token (e.g. paul), obtained with the Azure CLI:
  $env:SDLC_E2E_USER_TOKEN = az account get-access-token `
      --scope api://<ENTRA_API_CLIENT_ID>/access_as_user --query accessToken -o tsv
  uv run --env-file .env pytest tests/e2e/test_stage2_agent.py
(see docs/ENTRA_SETUP.md, "Stage 2d")
"""

import os
import urllib.request
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.e2e

AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents"
MCP_URL = os.environ.get("SDLC_MCP_URL", "http://127.0.0.1:8080/mcp")
USER_TOKEN = os.environ.get("SDLC_E2E_USER_TOKEN", "")


def _mcp_up() -> bool:
    try:
        with urllib.request.urlopen(MCP_URL.rsplit("/", 1)[0] + "/healthz", timeout=2):  # noqa: S310
            return True
    except OSError:
        return False


def _has_gemini() -> bool:
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE":
        return bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    return bool(os.environ.get("GOOGLE_API_KEY"))


@pytest.mark.skipif(not USER_TOKEN, reason="SDLC_E2E_USER_TOKEN not set (real Entra user token)")
@pytest.mark.skipif(not _has_gemini(), reason="no Gemini credentials")
@pytest.mark.skipif(not _mcp_up(), reason=f"MCP server not reachable at {MCP_URL}")
async def test_signed_in_user_runs_skill_through_mcp():
    from sdlc_web.app import create_app, verifier_from_env

    app = create_app(AGENTS_DIR, verifier_from_env(), host="127.0.0.1", port=8000)
    headers = {"X-Forwarded-Access-Token": USER_TOKEN}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://agent", timeout=180
    ) as web:
        session = (
            await web.post("/apps/bootstrap/users/user/sessions", headers=headers, json={})
        ).json()
        resp = await web.post(
            "/run",
            headers=headers,
            json={
                "appName": "bootstrap",  # camelCase, as the ADK dev UI sends it
                "userId": "user",
                "sessionId": session["id"],
                "newMessage": {
                    "role": "user",
                    "parts": [
                        {
                            "text": "Write a user story: finance analysts need to export "
                            "monthly invoices to CSV to reconcile them in a spreadsheet."
                        }
                    ],
                },
            },
        )
    assert resp.status_code == 200, resp.text
    events = resp.json()
    parts = [p for e in events for p in (e.get("content") or {}).get("parts", [])]
    calls = [p["functionCall"]["name"] for p in parts if p.get("functionCall")]
    errors = [
        p["functionResponse"]
        for p in parts
        if p.get("functionResponse") and "error" in str(p["functionResponse"]).lower()
    ]
    text = "".join(p.get("text", "") for p in parts)
    assert session["userId"] != "user"  # bound to the token's oid
    assert "list_skills" in calls and "load_skill" in calls, calls
    assert not errors, errors  # an MCP 401 would surface as a tool error
    assert "As a" in text and "Given" in text
