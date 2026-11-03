"""Test config: the repo config/ with a fixed test GroupMap (independent of any real tenant).

Fixture-only additions (see make_config_dir): the sdlc-platform team gets a group membership
(`platform-devs` -> developer) and a local `platform-infra` source, so tests have a second
group-based team with its own local data. The real sdlc-platform team has members only from
users.yaml and reads its code from GitHub (tests/config/test_repo_teams.py pins that)."""

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_CONFIG = REPO_ROOT / "config"

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
    teams: { payments: [developer] }
  direct-viewer:
    email: direct.viewer@example.com
    oid: "aaaaaaaa-0000-0000-0000-000000000002"
    roles: [viewer]
  pending:
    email: pending@example.com
    teams: { sdlc-platform: [developer] }
"""
# Fixture-only (not in the repo config): group members for sdlc-platform and its local source.
TEST_PLATFORM_MEMBERSHIP = """membership:
  - group: platform-devs
    roles: [developer]"""
TEST_PLATFORM_INFRA = """apiVersion: sdlc/v1
kind: Source
metadata:
  id: platform-infra
  owner_team: sdlc-platform
  description: test-only sample of platform infrastructure, CI docs and runbooks
spec:
  type: local_folder
  location: samples/sources/platform-infra
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


def make_config_dir(tmp_path: Path) -> Path:
    """Private, mutable copies of config/ and skills/ (skill paths resolve next to config/);
    env/local/groups.yaml uses the test group IDs."""
    dst = tmp_path / "config"
    shutil.copytree(REPO_CONFIG, dst)
    shutil.copytree(REPO_ROOT / "skills", tmp_path / "skills")
    shutil.copytree(REPO_ROOT / "samples", tmp_path / "samples")  # Source locations
    (dst / "env" / "local" / "groups.yaml").write_text(TEST_GROUPS_YAML, encoding="utf-8")
    (dst / "env" / "local" / "users.yaml").write_text(TEST_USERS_YAML, encoding="utf-8")
    team = dst / "teams" / "sdlc-platform.yaml"
    team.write_text(
        team.read_text(encoding="utf-8").replace("membership: []", TEST_PLATFORM_MEMBERSHIP),
        encoding="utf-8",
    )
    (dst / "sources" / "platform-infra.yaml").write_text(TEST_PLATFORM_INFRA, encoding="utf-8")
    return dst
