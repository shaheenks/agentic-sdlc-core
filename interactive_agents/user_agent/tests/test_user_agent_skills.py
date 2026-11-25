"""The skills in `skills/` (FR-SDLC-002, FR-SDLC-003, FR-SDLC-004): every one loads with ADK's own loader, the
stage skills cover what their requirements ask for, and the reviewers share one output contract, so the review
loop can merge their findings. The skills are read from the repository; this skips outside the workspace."""

import json
import re
from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parents[3] / "skills"
STAGES = {"brainstorm", "features-and-stories", "design-specification"}
REVIEWERS = {
    "review-structure",
    "review-style",
    "review-clarity",
    "review-design",
    "review-readiness",
    "review-technical-detail",
    "review-simplicity",
}


@pytest.fixture(scope="module")
def skills():
    if not SKILLS.is_dir():
        pytest.skip("skills/ not found: not running in the workspace")
    from google.adk.skills import load_skills_from_dir

    return {s.frontmatter.name: s for s in load_skills_from_dir(SKILLS)}


def test_every_skill_loads_and_is_named_after_its_folder(skills):
    assert set(skills) == STAGES | REVIEWERS
    for name in skills:
        assert (SKILLS / name / "SKILL.md").is_file()


def test_reviewers_share_the_findings_contract_and_credit_egm(skills):
    notice = (SKILLS / "NOTICE").read_text(encoding="utf-8")
    for name in REVIEWERS:
        skill = skills[name]
        assert skill.frontmatter.license == "Apache-2.0" and name in notice
        block = re.search(r"```json\n(.*?)\n```", skill.instructions, re.S)
        finding = json.loads(block.group(1))["findings"][0]
        assert set(finding) == {"severity", "location", "problem", "suggestion"}
        assert all(level in skill.instructions for level in ("`blocker`", "`major`", "`nit`"))
        assert "never see the conversation" in skill.instructions


def test_the_design_template_covers_what_fr_sdlc_003_asks_for(skills):
    text = skills["design-specification"].instructions
    for section in (
        "## Context",
        "## Goals",
        "## Non-goals",
        "### Components",
        "### Interfaces",
        "### Data",
        "### Flows",
        "## Alternatives considered",
        "## Security and privacy",
        "## Test approach",
        "## Rollout and operations",
        "## Risks",
        "## Open questions",
        "## Story coverage",
    ):
        assert section in text, section


def test_drafting_skills_never_write_to_jira_or_repositories_before_approval(skills):
    assert "Never create Jira issues" in skills["features-and-stories"].instructions
    assert "only after approval" in skills["design-specification"].instructions
