"""Team lens eval (version-03 P10 G8): a team's Goldfish lens catches what it exists for.

    SDLC_EVAL=1 uv run --env-file .env pytest tests/evals/test_team_lens_eval.py -s

Live Gemini (Vertex, ADC) against the in-process test MCP server (FakeEntra token, test config).
The sample draft in teams/payments/ stores and logs full card numbers and has no PCI impact
statement: the payments PCI lens must raise that as a blocker or major finding.
"""

import os
import re
from pathlib import Path

import pytest
from sdlc_agent.goldfish import make_goldfish_review
from sdlc_auth.adk import reset_request_token, set_request_token

from tests.support.entra import G_ENG_ALL, G_PAYMENTS_DEVS

pytestmark = pytest.mark.skipif(
    os.environ.get("SDLC_EVAL") != "1", reason="set SDLC_EVAL=1 (live Vertex)"
)

DRAFT = (Path(__file__).parent / "teams/payments/design_refund_retries.md").read_text()
PCI = re.compile(r"\b(pci|card ?(number|data)|pan|cardholder|mask)", re.IGNORECASE)


class Ctx:
    state: dict = {}
    user_id = "eval-user"

    class session:  # noqa: N801
        id = "eval-team-lens"


async def test_payments_pci_lens_flags_stored_card_numbers(base_url, entra):
    model = os.environ.get("SDLC_AGENT_MODEL", "gemini-3.8-flash")
    tool = make_goldfish_review(f"{base_url}/mcp", model, reviewer_tools=("whoami",))
    reset = set_request_token(entra.token(groups=[G_ENG_ALL, G_PAYMENTS_DEVS]))
    try:
        result = await tool.func(draft=DRAFT, tool_context=Ctx(), lenses=["payments-pci-lens"])
    finally:
        reset_request_token(reset)
    print("\n" + result.get("report_markdown", str(result)))
    assert result["lenses"][0] == {
        **result["lenses"][0],
        "lens": "payments-pci-lens",
        "status": "ok",
    }
    serious = result["findings"]["blocker"] + result["findings"]["major"]
    assert any(
        "payments-pci-lens" in f["lenses"] and PCI.search(f"{f['title']} {f.get('detail', '')}")
        for f in serious
    ), serious
