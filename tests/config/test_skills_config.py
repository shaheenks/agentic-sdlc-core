"""Stage 4a: SkillCatalog, team add-ons and the skill naming strategy."""

import shutil

import pytest
import yaml
from sdlc_config import ConfigError, load_snapshot

from tests.support.entra import TEST_ENV


def load(config_dir):
    return load_snapshot(config_dir, "local", TEST_ENV)


def edit_yaml(path, mutate):
    doc = yaml.safe_load(path.read_text())
    mutate(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def test_skills_and_addons_load(config_dir):
    snap = load(config_dir)
    assert set(snap.skills) == {
        "write-user-story",
        "test-case-gen",
        "design-review",
        "pci-checklist",
        "ledger-design-review",
        "infra-change-review",
    }
    assert snap.skills["pci-checklist"].team == "payments"
    assert snap.skills["design-review"].access_roles == {"lead"}
    assert snap.skills["write-user-story"].description.startswith("Turn a feature idea")
    assert "Given" in snap.skills["write-user-story"].instructions
    payments = snap.teams["payments"]
    assert payments.addon_skills == ("pci-checklist", "ledger-design-review")
    assert payments.instructions_source == "skills/teams/payments/AGENT_ADDENDUM.md"
    assert "pci-checklist" in payments.instructions
    assert payments.context["default_project"] == "payments"


def test_skill_content_is_part_of_the_version(config_dir):
    before = load(config_dir).version
    skill = config_dir.parent / "skills/core/test-case-gen/SKILL.md"
    skill.write_text(skill.read_text() + "\nOne more rule.\n")
    after = load(config_dir)
    assert after.version != before
    assert after.skills["test-case-gen"].instructions.endswith("One more rule.")


def test_addendum_is_part_of_the_version(config_dir):
    before = load(config_dir).version
    addendum = config_dir.parent / "skills/teams/platform/AGENT_ADDENDUM.md"
    addendum.write_text(addendum.read_text() + "\n- Be brief.\n")
    assert load(config_dir).version != before


def rename_frontmatter(config_dir, rel, new_name):
    path = config_dir.parent / rel
    text = path.read_text()
    old = text.split("name:", 1)[1].splitlines()[0].strip()
    path.write_text(text.replace(f"name: {old}", f"name: {new_name}", 1))


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        # naming: frontmatter name must equal the config key
        (
            lambda d: rename_frontmatter(d, "skills/core/test-case-gen/SKILL.md", "tests-gen"),
            "SKILL.md name 'tests-gen' must equal 'test-case-gen'",
        ),
        # naming: globally unique across the catalog and team add-ons
        (
            lambda d: edit_yaml(
                d / "teams/payments.yaml",
                lambda t: t["addons"]["skills"].update(
                    {"write-user-story": {"path": "skills/teams/payments/pci-checklist"}}
                ),
            ),
            "skill name 'write-user-story' is already used by skills.yaml",
        ),
        # naming: folder name must equal the config key
        (
            lambda d: edit_yaml(
                d / "skills.yaml",
                lambda s: s["skills"].update(
                    {"story-writer": {"path": "skills/core/write-user-story"}}
                ),
            ),
            "folder 'write-user-story' must be named 'story-writer'",
        ),
        # naming: lowercase kebab-case only
        (
            lambda d: edit_yaml(
                d / "skills.yaml",
                lambda s: s["skills"].update({"Bad_Name": {"path": "skills/core/x"}}),
            ),
            "Bad_Name",
        ),
        # paths stay inside skills/
        (
            lambda d: edit_yaml(
                d / "skills.yaml",
                lambda s: s["skills"].update({"escape": {"path": "config/roles"}}),
            ),
            "skills/escape/path",
        ),
        (
            lambda d: edit_yaml(
                d / "skills.yaml",
                lambda s: s["skills"].update({"ghost": {"path": "skills/core/ghost"}}),
            ),
            "skills/core/ghost/SKILL.md not found",
        ),
        (
            lambda d: edit_yaml(
                d / "skills.yaml",
                lambda s: s["skills"]["design-review"].update(access={"roles": ["overlord"]}),
            ),
            "unknown role 'overlord'",
        ),
        (
            lambda d: edit_yaml(
                d / "skills.yaml",
                lambda s: s["skills"]["design-review"].update(access={"teams": ["marketing"]}),
            ),
            "unknown team 'marketing'",
        ),
        (
            lambda d: edit_yaml(
                d / "roles.yaml",
                lambda r: r["roles"]["viewer"]["skills"].update(allow=["tag:finance"]),
            ),
            "unknown tag 'finance'",
        ),
        (
            lambda d: edit_yaml(
                d / "roles.yaml",
                lambda r: r["roles"]["viewer"]["skills"].update(allow=["pci-checklist"]),
            ),
            "team add-ons are granted by team membership",
        ),
        (
            lambda d: edit_yaml(
                d / "teams/platform.yaml",
                lambda t: t["addons"].update(instructions="skills/teams/platform/MISSING.md"),
            ),
            "file not found",
        ),
        (
            lambda d: edit_yaml(
                d / "teams/payments.yaml",
                lambda t: t["addons"]["skills"]["ledger-design-review"].update(
                    access={"roles": ["cfo"]}
                ),
            ),
            "unknown role 'cfo'",
        ),
        (
            lambda d: (d.parent / "skills/core/design-review/SKILL.md").write_text(
                "no frontmatter"
            ),
            "missing YAML frontmatter",
        ),
    ],
)
def test_bad_skill_config_fails(config_dir, mutate, message):
    mutate(config_dir)
    with pytest.raises(ConfigError) as exc:
        load(config_dir)
    assert message in str(exc.value), exc.value


def test_skills_folder_symlink_escape_is_refused(config_dir, tmp_path):
    outside = tmp_path / "outside" / "evil"
    outside.mkdir(parents=True)
    (outside / "SKILL.md").write_text("---\nname: evil\ndescription: x\n---\nsteal")
    link = config_dir.parent / "skills/core/evil"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not permitted on this machine")
    edit_yaml(
        config_dir / "skills.yaml",
        lambda s: s["skills"].update({"evil": {"path": "skills/core/evil"}}),
    )
    with pytest.raises(ConfigError, match="must stay inside skills/"):
        load(config_dir)


def test_team_without_addons_is_fine(config_dir):
    edit_yaml(config_dir / "teams/platform.yaml", lambda t: t.pop("addons"))
    shutil.rmtree(config_dir.parent / "skills/teams/platform")
    snap = load(config_dir)
    assert snap.teams["platform"].addon_skills == () and snap.teams["platform"].instructions is None
