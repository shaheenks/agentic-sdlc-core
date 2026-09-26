"""Test config: the repo config/ with a fixed test GroupMap (independent of any real tenant)."""

import shutil
from pathlib import Path

REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"

TEST_GROUPS_YAML = """apiVersion: sdlc/v1
kind: GroupMap
groups:
  eng-all:         { id: "00000000-0000-0000-0000-000000000001" }
  payments-devs:   { id: "00000000-0000-0000-0000-000000000002" }
  payments-leads:  { id: "00000000-0000-0000-0000-000000000003" }
  platform-devs:   { id: "00000000-0000-0000-0000-000000000004" }
  platform-admins: { id: "00000000-0000-0000-0000-000000000005" }
"""


def make_config_dir(tmp_path: Path) -> Path:
    """Private, mutable copy of config/ whose env/local/groups.yaml uses the test group IDs."""
    dst = tmp_path / "config"
    shutil.copytree(REPO_CONFIG, dst)
    (dst / "env" / "local" / "groups.yaml").write_text(TEST_GROUPS_YAML, encoding="utf-8")
    return dst
