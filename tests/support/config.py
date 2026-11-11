"""Test config: the repo config/ with a fixed test GroupMap (independent of any real tenant).

Fixture-only additions (see make_config_dir): the sdlc-platform team gets a group membership
(`platform-devs` -> member) and a local `platform-infra` source, so tests have a second
group-based team with its own local data. The real sdlc-platform team has members only from
app roles and users.yaml and reads its code from GitHub (tests/config/test_repo_teams.py pins that).
The repo's gcs sources read their copies in tests/fixtures/sample_sources instead
(use_sample_folders); make_config_dir copies that folder to <tmp>/sample_sources."""

import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_CONFIG = REPO_ROOT / "config"
SAMPLES_DIR = REPO_ROOT / "tests" / "fixtures" / "sample_sources"  # synthetic test corpus

TEST_GROUPS_YAML = """apiVersion: sdlc/v1
kind: GroupMap
groups:
  eng-all:         { id: "00000000-0000-0000-0000-000000000001" }
  payments-devs:   { id: "00000000-0000-0000-0000-000000000002" }
  payments-leads:  { id: "00000000-0000-0000-0000-000000000003" }
  platform-devs:   { id: "00000000-0000-0000-0000-000000000004" }
  platform-admins: { id: "00000000-0000-0000-0000-000000000005" }
  infra-readers:   { id: "00000000-0000-0000-0000-000000000006" }
"""

# Direct members (users.yaml), matched by oid. "pending" has no oid yet: it must grant nothing.
TEST_USERS_YAML = """apiVersion: sdlc/v1
kind: UserMap
users:
  direct-dev:
    email: direct.dev@example.com
    oid: "aaaaaaaa-0000-0000-0000-000000000001"
    teams: { payments: [member] }
  direct-viewer:
    email: direct.viewer@example.com
    oid: "aaaaaaaa-0000-0000-0000-000000000002"
    roles: [viewer]
  pending:
    email: pending@example.com
    teams: { sdlc-platform: [member] }
"""
# Fixture-only (not in the repo config): group members for sdlc-platform and its local source.
TEST_PLATFORM_MEMBERSHIP = """membership:
  - group: platform-devs
    roles: [member]
"""
TEST_PLATFORM_INFRA = """apiVersion: sdlc/v1
kind: Source
metadata:
  id: platform-infra
  owner_team: sdlc-platform
  description: test-only sample of platform infrastructure, CI docs and runbooks
spec:
  type: local_folder
  location: sample_sources/platform-infra
  include: ["**/*.md", "**/*.tf", "**/*.pdf"]
  classification: internal
  ingest:
    chunking: { strategy: auto, max_tokens: 400, overlap: 40 }
    pdf: { ocr: gemini }
    graph:
      enabled: true
      entity_types: [service, component, data_store, environment, runbook, metric, team, alert]
access:
  teams: [sdlc-platform]
  groups: [infra-readers]
  roles: [admin]
"""
DIRECT_DEV_OID = "aaaaaaaa-0000-0000-0000-000000000001"

# Fixture-only tools (CH-0003): the policy engine's argument limits, role inheritance, denies and
# audit are tested on two tools that exist only in tests. The real catalog has no team-constrained
# tool. `fixture_review` is a member tool, `fixture_approve` an approver tool; both take a `repo`
# that each team limits to its own repositories. The test MCP server registers echo versions.
FIXTURE_TOOLS_YAML = """  # fixture-only (tests/support/config.py)
  fixture_review:  { server: core-mcp, risk: medium, args: { repo: { type: string } } }
  fixture_approve: { server: core-mcp, risk: high,   args: { repo: { type: string } } }
"""
FIXTURE_REPOS = {
    "payments": ["payments-api", "payments-ui"],
    "sdlc-platform": ["agentic-sdlc-core"],
    "webapp": ["full-stack-fastapi-template"],
}
FIXTURE_APPROVE_TEAMS = ("payments", "webapp")  # sdlc-platform does not limit fixture_approve
_TEAM_DENY = re.compile(r"(    deny: \[\][^\n]*\n)")


def add_fixture_tools(config_dir: Path) -> None:
    tools = config_dir / "tools.yaml"
    tools.write_text(tools.read_text(encoding="utf-8") + FIXTURE_TOOLS_YAML, encoding="utf-8")
    roles = config_dir / "roles.yaml"
    text = roles.read_text(encoding="utf-8")
    text = text.replace("allow: [jira_get_issue,", "allow: [fixture_review, jira_get_issue,", 1)
    text = text.replace(
        "    inherits: [member]\n",
        "    inherits: [member]\n    tools:  { allow: [fixture_approve] }\n",
        1,
    )
    assert "fixture_review" in text and "fixture_approve" in text, "roles.yaml layout changed"
    roles.write_text(text, encoding="utf-8")
    for team, repos in FIXTURE_REPOS.items():
        tools_limited = ["fixture_review"]
        if team in FIXTURE_APPROVE_TEAMS:
            tools_limited.append("fixture_approve")
        block = "    constraints:\n" + "".join(
            f"      {tool}:\n        args:\n          repo: {{ in: [{', '.join(repos)}] }}\n"
            for tool in tools_limited
        )
        path = config_dir / "teams" / f"{team}.yaml"
        text, n = _TEAM_DENY.subn(lambda m, b=block: m.group(1) + b, path.read_text("utf-8"))
        assert n == 1, f"{path.name}: expected one policy/tools/deny line"
        path.write_text(text, encoding="utf-8")


def fixture_result(tool: str, **inputs) -> dict:
    """What the fixture tools return (tests monkeypatch it to make a tool fail)."""
    return {"fixture": True, "tool": tool, "inputs": inputs}


def fixture_review(repo: str, ref: str = "main") -> dict:
    """(Test fixture) Echo a review request."""
    return fixture_result("fixture_review", repo=repo, ref=ref)


def fixture_approve(repo: str, design_id: str) -> dict:
    """(Test fixture) Echo an approval."""
    return fixture_result("fixture_approve", repo=repo, design_id=design_id)


# The repo sources read gs://<config store>/source_docs/<id>/ (version-02 N14); tests have no
# GCS, so they read the same documents from SAMPLES_DIR (folder names below).
SAMPLE_FOLDERS = {
    "eng-standards": "eng-standards",
    "payments-code": "payments-api",
    "payments-incidents": "payments-incidents",
}
_GCS_SPEC = re.compile(r"  type: gcs\r?\n  location: gs://\S+")


def use_sample_folders(config_dir: Path) -> None:
    for source_id, folder in SAMPLE_FOLDERS.items():
        path = config_dir / "sources" / f"{source_id}.yaml"
        local = f"  type: local_folder\n  location: sample_sources/{folder}"
        text, n = _GCS_SPEC.subn(local, path.read_text(encoding="utf-8"))
        assert n == 1, f"{path.name}: expected one gcs location"
        path.write_text(text, encoding="utf-8")


def make_config_dir(tmp_path: Path, fixture_tools: bool = True) -> Path:
    """Private, mutable copies of config/ and skills/ (skill paths resolve next to config/);
    env/local/groups.yaml uses the test group IDs. fixture_tools=False keeps the real catalog
    (the persona matrix pins the real access model)."""
    dst = tmp_path / "config"
    shutil.copytree(REPO_CONFIG, dst)
    shutil.copytree(REPO_ROOT / "skills", tmp_path / "skills")
    shutil.copytree(SAMPLES_DIR, tmp_path / "sample_sources")  # local source locations
    (dst / "env" / "local" / "groups.yaml").write_text(TEST_GROUPS_YAML, encoding="utf-8")
    (dst / "env" / "local" / "users.yaml").write_text(TEST_USERS_YAML, encoding="utf-8")
    team = dst / "teams" / "sdlc-platform.yaml"
    team.write_text(
        team.read_text(encoding="utf-8").replace("membership:\n", TEST_PLATFORM_MEMBERSHIP, 1),
        encoding="utf-8",
    )
    (dst / "sources" / "platform-infra.yaml").write_text(TEST_PLATFORM_INFRA, encoding="utf-8")
    use_sample_folders(dst)
    if fixture_tools:
        add_fixture_tools(dst)
    return dst
