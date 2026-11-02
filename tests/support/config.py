"""Test config: the repo config/ with a fixed test GroupMap (independent of any real tenant)."""

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
    teams: { platform: [developer] }
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
    return dst
