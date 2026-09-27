"""Stage 3a: RoleSet, ToolCatalog and Team kinds, schemas and cross-reference checks."""

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


def test_repo_rbac_config_loads(config_dir):
    snap = load(config_dir)
    assert {"viewer", "developer", "lead", "admin"} <= set(snap.roles)
    assert snap.roles["developer"].inherits == ("viewer",)
    assert snap.roles["admin"].unconstrained and "*" in snap.roles["admin"].tools_allow
    assert snap.tools["review_code"].args == {"repo"}
    assert set(snap.teams) >= {"payments", "platform"}
    payments = snap.teams["payments"]
    assert payments.constraints["review_code"]["repo"] == {"payments-api", "payments-ui"}
    assert payments.membership[0].rule == "teams/payments.yaml#membership[0]"
    assert payments.membership[0].team == "payments"
    assert str(snap.bindings[0].ref) == "everyone:*"
    assert str(snap.bindings[1].ref) == "group:eng-all"


def test_app_role_bindings_are_accepted(config_dir):
    edit_yaml(
        config_dir / "roles.yaml",
        lambda d: d["bindings"].append({"app_role": "SDLC.Admin", "roles": ["admin"]}),
    )
    edit_yaml(
        config_dir / "teams/payments.yaml",
        lambda d: d["membership"].append(
            {"app_role": "SDLC.Payments.Developer", "roles": ["developer"]}
        ),
    )
    snap = load(config_dir)
    assert str(snap.bindings[-1].ref) == "app_role:SDLC.Admin"
    assert str(snap.teams["payments"].membership[-1].ref) == "app_role:SDLC.Payments.Developer"


@pytest.mark.parametrize(
    ("file", "mutate", "message"),
    [
        (
            "roles.yaml",
            lambda d: d["roles"]["viewer"]["tools"]["allow"].append("nuke_prod"),
            "unknown tool 'nuke_prod'",
        ),
        (
            "roles.yaml",
            lambda d: d["bindings"].append({"group": "ghosts", "roles": ["viewer"]}),
            "unknown group alias 'ghosts'",
        ),
        (
            "roles.yaml",
            lambda d: d["bindings"].append({"group": "eng-all", "roles": ["god"]}),
            "unknown role 'god'",
        ),
        (
            "roles.yaml",
            lambda d: d["roles"]["viewer"].update(inherits=["admin"]),
            "role inheritance cycle",
        ),
        (
            "roles.yaml",
            lambda d: d["roles"]["lead"].update(inherits=["boss"]),
            "unknown role 'boss'",
        ),
        (
            "roles.yaml",
            lambda d: d["roles"]["viewer"]["data"].update(max_classification="secret"),
            "max_classification: unknown 'secret'",
        ),
        (
            "roles.yaml",
            lambda d: d["bindings"].append(
                {"group": "eng-all", "app_role": "X", "roles": ["viewer"]}
            ),
            "bindings/",
        ),
        (
            "tools.yaml",
            lambda d: d["tools"]["ping"].update(server="nowhere"),
            "unknown server 'nowhere'",
        ),
        ("tools.yaml", lambda d: d["tools"]["ping"].update(risk="extreme"), "tools/ping/risk"),
        (
            "teams/payments.yaml",
            lambda d: d["membership"].append({"group": "payments-devs", "roles": ["overlord"]}),
            "unknown role 'overlord'",
        ),
        (
            "teams/payments.yaml",
            lambda d: d["metadata"].update(owners=["nobody"]),
            "metadata/owners: unknown group alias 'nobody'",
        ),
        (
            "teams/payments.yaml",
            lambda d: d["metadata"].update(name="billing"),
            "must match the file name",
        ),
        (
            "teams/payments.yaml",
            lambda d: d["policy"]["tools"]["constraints"]["review_code"]["args"].update(
                branch={"in": ["main"]}
            ),
            "argument 'branch' is not declared",
        ),
        (
            "teams/payments.yaml",
            lambda d: d["policy"]["tools"]["constraints"].update(
                ghost_tool={"args": {"x": {"in": ["y"]}}}
            ),
            "unknown tool 'ghost_tool'",
        ),
        (
            "teams/payments.yaml",
            lambda d: d["policy"]["tools"].update(deny=["*"]),
            "policy/tools/deny",
        ),
        ("teams/payments.yaml", lambda d: d["addons"].update(surprise=True), "addons"),
    ],
)
def test_bad_rbac_config_fails(config_dir, file, mutate, message):
    edit_yaml(config_dir / file, mutate)
    with pytest.raises(ConfigError) as exc:
        load(config_dir)
    assert message in str(exc.value), exc.value


def test_teams_folder_may_be_empty(config_dir):
    # sources reference teams (owner_team, access), so they go too
    for folder in ("teams", "sources"):
        for path in (config_dir / folder).glob("*.yaml"):
            path.unlink()
    snap = load(config_dir)
    assert snap.teams == {} and snap.sources == {}


def test_all_problems_reported_together(config_dir):
    edit_yaml(
        config_dir / "roles.yaml", lambda d: d["roles"]["viewer"]["tools"]["allow"].append("a")
    )
    edit_yaml(config_dir / "teams/platform.yaml", lambda d: d["metadata"].update(owners=["zz"]))
    with pytest.raises(ConfigError) as exc:
        load(config_dir)
    assert len(exc.value.problems) >= 2
