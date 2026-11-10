"""The repo config itself (not the test fixture): teams, their members and the team sources.

tests/support/config.py adds fixture-only group membership and a local source to sdlc-platform;
these tests read config/ directly so the real setup stays pinned."""

from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parents[2] / "config"


def doc(rel: str) -> dict:
    return yaml.safe_load((CONFIG / rel).read_text(encoding="utf-8"))


def test_teams():
    assert {p.stem for p in (CONFIG / "teams").glob("*.yaml")} == {
        "payments",
        "sdlc-platform",
        "webapp",
    }


def test_sdlc_platform_members_come_from_app_roles_and_users_yaml():
    team = doc("teams/sdlc-platform.yaml")
    # no Entra group per role: app roles (version-03 P2 E1) + env/<env>/users.yaml
    assert team["membership"] == [
        {"app_role": "SDLC.Platform.Developer", "roles": ["developer"]},
        {"app_role": "SDLC.Platform.Lead", "roles": ["lead"]},
    ]
    assert team["addons"]["skills"] == {
        "infra-change-review": {"path": "skills/teams/sdlc-platform/infra-change-review"}
    }
    repos = {t: c["args"]["repo"]["in"] for t, c in team["policy"]["tools"]["constraints"].items()}
    assert repos == {"review_code": ["agentic-sdlc-core"], "generate_tests": ["agentic-sdlc-core"]}


def test_sdlc_platform_sources():
    owned = {
        p.stem
        for p in (CONFIG / "sources").glob("*.yaml")
        if doc(f"sources/{p.name}")["metadata"]["owner_team"] == "sdlc-platform"
    }
    assert owned == {"sdlc-platform", "eng-standards"}
    source = doc("sources/sdlc-platform.yaml")
    assert source["spec"]["location"] == "https://github.com/shaheenks/agentic-sdlc-core.git"
    assert source["spec"]["ref"] == "main" and "credentials" not in source["spec"]
    assert "github.com" in doc("platform.yaml")["knowledge"]["allowed_hosts"]


def test_webapp_team():
    """webapp: full-stack-fastapi-template; app roles + users.yaml, no group.

    The worked example in docs/guides/TEAM_ONBOARDING.md."""
    team = doc("teams/webapp.yaml")
    assert team["membership"] == [
        {"app_role": "SDLC.Webapp.Developer", "roles": ["developer"]},
        {"app_role": "SDLC.Webapp.Lead", "roles": ["lead"]},
    ]
    repos = {t: c["args"]["repo"]["in"] for t, c in team["policy"]["tools"]["constraints"].items()}
    limited = ("review_code", "generate_tests", "approve_design")
    assert repos == {t: ["full-stack-fastapi-template"] for t in limited}
    addons = team["addons"]
    tags = {name: s.get("tags", []) for name, s in addons["skills"].items()}
    assert tags == {
        "webapp-coding-standards": [],
        "webapp-code-review": [],
        "webapp-api-lens": ["goldfish-lens"],
        "webapp-design-template": ["doc-template"],
        "webapp-story-template": ["doc-template"],
    }
    types = addons["flows"]["document"]["types"]
    assert types["design"]["template"] == "webapp-design-template"
    assert types["design"]["required_lenses"] == ["webapp-api-lens"]
    assert types["user-story"]["template"] == "webapp-story-template"
    assert (
        addons["context"]["repository"]
        == "https://github.com/shaheenks/full-stack-fastapi-template"
    )


def test_webapp_sources():
    owned = {
        p.stem
        for p in (CONFIG / "sources").glob("*.yaml")
        if doc(f"sources/{p.name}")["metadata"]["owner_team"] == "webapp"
    }
    assert owned == {"webapp-code"}
    source = doc("sources/webapp-code.yaml")
    assert (
        source["spec"]["location"] == "https://github.com/shaheenks/full-stack-fastapi-template.git"
    )
    assert source["spec"]["ref"] == "master" and "credentials" not in source["spec"]
    assert "frontend/src/client/**" in source["spec"]["exclude"]  # generated code
    assert source["access"] == {"teams": ["webapp"], "roles": ["admin"]}


def test_sample_sources_read_the_config_store_bucket():
    """version-02 N14: one-time move of samples/ to gs://<config store>/source_docs/<id>/;
    tests read the repo copy instead (tests/fixtures/sample_sources, SAMPLE_FOLDERS)."""
    from tests.support.config import SAMPLE_FOLDERS, SAMPLES_DIR

    for source_id, folder in SAMPLE_FOLDERS.items():
        spec = doc(f"sources/{source_id}.yaml")["spec"]
        assert spec["type"] == "gcs"
        assert spec["location"] == f"gs://sdlc-config-store-a7484d8b/source_docs/{source_id}/"
        assert (SAMPLES_DIR / folder).is_dir()
