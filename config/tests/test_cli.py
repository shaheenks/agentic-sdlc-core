import json
import shutil

import pytest
import yaml
from sdlc_config import CONFIG_DIR, compile_config
from sdlc_config.cli import main


@pytest.fixture
def config_dir(tmp_path):
    """A copy of the repository's configuration, to change in a test."""
    target = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, target, ignore=shutil.ignore_patterns("src", "tests", "*.toml", "*.md", "local", "dev"))
    return target


def edit(path, change):
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(doc)
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")


def test_repository_config_validates_for_the_example_environment(capsys):
    assert main(["validate", "--env", "example"]) == 0
    assert "config ok" in capsys.readouterr().out


def test_compiled_config_lists_members_with_their_roles():
    config = compile_config(CONFIG_DIR, "example").config
    # ada leads payments, and early-adopters lists payments:lead
    assert config["members"]["ada@example.test"] == {
        "teams": {"payments": ["lead", "member"]},
        "user_groups": ["early-adopters"],
    }
    assert config["members"]["grace@example.test"]["user_groups"] == ["early-adopters"]
    assert config["identity"]["mode"] == "caller_token"
    assert config["identity"]["callers"]["sdlc_ui"] == ["sdlc-ui@example-project.iam.gserviceaccount.com"]


def test_trusted_header_is_refused_outside_local(config_dir, capsys):
    edit(config_dir / "env/example/identity.yaml", lambda d: d.update({"mode": "trusted_header"}))
    assert main(["validate", "--env", "example", "--dir", str(config_dir)]) == 1
    assert "only in the local environment" in capsys.readouterr().err


def test_missing_environment_warns_but_validates(config_dir, capsys):
    assert main(["validate", "--env", "nowhere", "--dir", str(config_dir)]) == 0
    assert "refuse every user" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("file", "change", "message"),
    [
        (
            "env/example/teams/payments.yaml",
            lambda d: d.update({"sources": ["ghost"]}),
            "unknown source 'ghost'",
        ),
        (
            "env/example/teams/platform.yaml",
            lambda d: d.pop("name"),
            "env/example/teams/platform.yaml: teams/platform: 'name' is a required property",
        ),
        (
            "env/example/teams/payments.yaml",
            lambda d: d["systems"]["jira"][0].update({"provider": "github"}),
            "not a Jira provider",
        ),
        (
            "env/example/teams/payments.yaml",
            lambda d: d["systems"]["repositories"].append(
                {"provider": "bitbucket_dc", "repo": "P/s", "design_path": "d"}
            ),
            "needs base_url",
        ),
        (
            "env/example/teams/payments.yaml",
            lambda d: d["systems"]["jira"][1].update({"default": True}),
            "jira: more than one default (PAY, CARD)",
        ),
        (
            "env/example/teams/payments.yaml",
            lambda d: d["systems"]["repositories"][0].pop("default"),
            "repositories: mark one entry `default: true`",
        ),
        (
            "env/example/teams/payments.yaml",
            lambda d: d["systems"]["jira"][1].update({"project": "PAY"}),
            "Jira project 'PAY' is listed twice",
        ),
        (
            "env/example/teams/payments.yaml",
            lambda d: d["systems"]["confluence"][0].update({"provider": "jira_cloud"}),
            "'jira_cloud' is not a Confluence provider",
        ),
        (
            "env/example/teams/payments.yaml",
            lambda d: d["systems"]["control_repo"].update({"provider": "jira_cloud"}),
            "control_repo: 'jira_cloud' is not a repository provider",
        ),
        (
            "env/example/teams/payments.yaml",
            lambda d: d["systems"]["control_repo"].update({"repo": "example-org/payments-service"}),
            "is also a product repository",
        ),
        (
            "env/example/teams/payments.yaml",
            lambda d: d.update({"role_grants": {"boss": {"tool_groups": ["jira"]}}}),
            "has no role 'boss'",
        ),
        (
            "env/example/user_groups.yaml",
            lambda d: d["user_groups"]["early-adopters"].update({"teams": ["payments:boss", "nope"]}),
            "env/example/user_groups.yaml: early-adopters: teams: team 'payments' has no role 'boss'",
        ),
        (
            "env/example/user_groups.yaml",
            lambda d: d["user_groups"]["early-adopters"].update({"teams": ["nope"]}),
            "early-adopters: teams: unknown team 'nope'",
        ),
        (
            "env/example/user_groups.yaml",
            lambda d: d["user_groups"]["early-adopters"].update({"tool_groups": ["ghost"]}),
            "env/example/user_groups.yaml: early-adopters: unknown tool group 'ghost'",
        ),
        ("surfaces.yaml", lambda d: d["surfaces"]["sdlc_ui"]["tool_groups"].append("ghost"), "unknown tool group"),
        ("surfaces.yaml", lambda d: d["surfaces"]["sdlc_ui"].pop("description"), "'description' is a required"),
        ("env/example/identity.yaml", lambda d: d["callers"].update({"desktop": ["x"]}), "unknown surface 'desktop'"),
        (
            "env/example/identity.yaml",
            lambda d: d["callers"]["user_agent"].append(d["callers"]["sdlc_ui"][0]),
            "is in",
        ),
        (
            "env/example/users.yaml",
            lambda d: d["users"]["ada@example.test"]["teams"].append("payments:boss"),
            "no role",
        ),
        (
            "env/example/users.yaml",
            lambda d: d["users"]["ada@example.test"].update({"teams": ["nope"]}),
            "unknown team",
        ),
        (
            "env/example/users.yaml",
            lambda d: d["users"]["ada@example.test"].update({"user_groups": ["ghosts"]}),
            "unknown user group 'ghosts'",
        ),
        ("tool_groups.yaml", lambda d: d["tool_groups"]["identity"]["tools"].append("artifact_list"), "in both"),
        # DEC-0015: the system identity and the subscriptions
        (
            "env/example/system.yaml",
            lambda d: d["teams"].append("nope"),
            "env/example/system.yaml: unknown team 'nope'",
        ),
        (
            "env/example/system.yaml",
            lambda d: d["tool_groups"].append("control"),
            "tool group 'control' is on no system surface",
        ),
        (
            "env/example/system.yaml",
            lambda d: d["tool_groups"].remove("code_workspace"),
            "ci_implement: writes ['workspace_run'] are not tools the system identity is given",
        ),
        (
            "env/example/system.yaml",
            lambda d: d["machine_users"].update({"gitlab": "bot"}),
            "machine_users: unknown provider 'gitlab'",
        ),
        (
            "subscriptions.yaml",
            lambda d: d["subscriptions"]["ci_plan"]["filters"].update({"head_branch": "^sdlc/(?P<who>.+)$"}),
            "ci_plan: filters.head_branch: unknown run inputs ['who']",
        ),
        (
            "subscriptions.yaml",
            lambda d: d["subscriptions"]["ci_plan"]["filters"].update({"base_branch": "^feature/("}),
            "ci_plan: filters.base_branch: not a regular expression",
        ),
        ("subscriptions.yaml", lambda d: d["subscriptions"]["ci_plan"].update({"writes": []}), "should be non-empty"),
        (
            "env/example/teams/payments.yaml",
            lambda d: d["systems"]["repositories"][0]["workspace"].pop("test"),
            "'test' is a required property",
        ),
    ],
)
def test_invalid_configuration_fails(config_dir, file, change, message, capsys):
    edit(config_dir / file, change)
    assert main(["validate", "--env", "example", "--dir", str(config_dir)]) == 1
    assert message in capsys.readouterr().err


def test_broken_yaml_fails(config_dir):
    (config_dir / "env/example/teams/payments.yaml").write_text("roles: [1, 2", encoding="utf-8")
    assert main(["validate", "--env", "example", "--dir", str(config_dir)]) == 1


def test_publish_activate_and_roll_back(tmp_path, config_dir, capsys):
    store = tmp_path / "bundles"
    assert main(["publish", "--env", "example", "--to", str(store), "--activate", "--by", "tester"]) == 0
    first = json.loads((store / "active.json").read_text())["version"]

    edit(config_dir / "limits.yaml", lambda d: d["rate_limits"]["tool_calls"].update({"per_user_per_minute": 5}))
    assert main(["publish", "--env", "example", "--dir", str(config_dir), "--to", str(store), "--activate"]) == 0
    pointer = json.loads((store / "active.json").read_text())
    assert pointer["version"] != first and pointer["previous"] == first

    assert main(["activate", "--env", "example", "--to", str(store), "--version", first, "--by", "tester"]) == 0
    assert json.loads((store / "active.json").read_text())["version"] == first
    assert len(list((store / "activations").iterdir())) == 3
    assert '"event": "config.activate"' in capsys.readouterr().out


def test_activate_refuses_a_bundle_of_another_environment(tmp_path, config_dir):
    store = tmp_path / "bundles"
    assert main(["publish", "--env", "example", "--to", str(store)]) == 0
    version = next((store / "bundles").iterdir()).stem
    assert main(["activate", "--env", "dev", "--to", str(store), "--version", version]) == 1
    assert not (store / "active.json").exists()


def test_environment_teams_add_systems_to_shared_teams():
    config = compile_config(CONFIG_DIR, "example").config
    assert config["teams"]["payments"] == {
        "name": "Payments",
        "description": "Payment services.",
        "roles": ["member", "lead"],
        "sources": ["payments-code"],
        "role_grants": {"lead": {"sources": ["ledger-docs"]}},
    }
    systems = config["team_systems"]["payments"]
    assert [(j["project"], j["default"]) for j in systems["jira"]] == [("PAY", True), ("CARD", False)]
    assert (systems["jira"][0]["epic_type"], systems["jira"][0]["feature_type"], systems["jira"][0]["story_type"]) == (
        "Epic",
        "Story",
        "Sub-task",
    )
    assert systems["confluence"][0]["default"] is True  # the only entry
    assert [r["default"] for r in systems["repositories"]] == [True, False]
    assert systems["control_repo"] == {
        "provider": "github",
        "repo": "example-org/payments-sdlc-control",
        "branch": "main",
        "system_accounts": ["example-sdlc-bot"],  # the machine user never approves (DEC-0015)
    }
    assert "platform" not in config["team_systems"]


def test_grants_compile_from_teams_user_groups_and_everyone(config_dir):
    edit(
        config_dir / "env/example/teams/payments.yaml",
        lambda d: d.update({"sources": ["platform-spec"], "role_grants": {"lead": {"tool_groups": ["jira"]}}}),
    )
    edit(
        config_dir / "env/example/user_groups.yaml",
        lambda d: d["user_groups"]["early-adopters"].update({"tool_groups": ["jira"]}),
    )
    grants = {g["id"]: g for g in compile_config(config_dir, "example").config["grants"]}
    assert grants["everyone"]["to"] == {"everyone": True}
    assert "knowledge" in grants["everyone"]["tool_groups"] and grants["everyone"]["sources"] == [
        "platform-spec",
        "platform-wiki",
    ]
    assert grants["team:payments"] == {
        "id": "team:payments",
        "sources": ["platform-spec"],
        "to": {"teams": ["payments"]},
    }
    assert grants["team:payments:lead"]["to"] == {"teams": ["payments:lead"]}
    assert grants["user_group:early-adopters"]["to"] == {"user_groups": ["early-adopters"]}
    assert "team:platform" not in grants  # given nothing


def test_an_old_systems_file_is_refused(config_dir, capsys):
    (config_dir / "env/example/systems.yaml").write_text("teams: {}\n", encoding="utf-8")
    assert main(["validate", "--env", "example", "--dir", str(config_dir)]) == 1
    assert "moved to `systems` in env/example/teams.yaml" in capsys.readouterr().err


def test_teams_user_groups_and_sources_belong_to_the_environment(config_dir, capsys):
    nowhere = compile_config(config_dir, "nowhere")
    assert nowhere.ok and not (nowhere.config["teams"] or nowhere.config["user_groups"] or nowhere.config["sources"])
    for kind in ("teams", "user_groups", "sources"):
        (config_dir / f"{kind}.yaml").write_text(f"{kind}: {{}}\n", encoding="utf-8")
    assert main(["validate", "--env", "example", "--dir", str(config_dir)]) == 1
    err = capsys.readouterr().err
    assert all(f"move it to env/example/{kind}.yaml" in err for kind in ("teams", "user_groups", "sources"))


def test_teams_and_sources_can_be_one_file_each_next_to_a_list(config_dir, capsys):
    env = config_dir / "env/example"
    (env / "teams.yaml").write_text(
        yaml.safe_dump({"teams": {"risk": {"name": "Risk", "description": "Risk.", "roles": ["member"]}}}),
        encoding="utf-8",
    )
    (env / "sources/risk-docs.yml").write_text(
        yaml.safe_dump(
            {
                "name": "Risk docs",
                "description": "-",
                "kind": "folder",
                "location": "risk",
                "classification": "internal",
            }
        ),
        encoding="utf-8",
    )
    (env / "teams/README.md").write_text("not configuration", encoding="utf-8")
    config = compile_config(config_dir, "example").config
    assert set(config["teams"]) == {"payments", "platform", "risk"}
    assert config["team_systems"]["payments"]["control_repo"]["repo"] == "example-org/payments-sdlc-control"
    assert set(config["sources"]) == {"platform-spec", "platform-wiki", "payments-code", "ledger-docs", "risk-docs"}

    (env / "teams/risk.yaml").write_text(
        yaml.safe_dump({"name": "Risk", "description": "Risk.", "roles": ["member"]}), encoding="utf-8"
    )
    (env / "teams/Bad Name.yaml").write_text(
        yaml.safe_dump({"name": "Bad", "description": "-", "roles": ["member"]}), encoding="utf-8"
    )
    assert main(["validate", "--env", "example", "--dir", str(config_dir)]) == 1
    err = capsys.readouterr().err
    assert "env/example/teams/risk.yaml: 'risk' is also defined in env/example/teams.yaml" in err
    assert "env/example/teams/Bad Name.yaml" in err


def test_a_user_group_takes_in_the_members_of_the_teams_it_lists(config_dir):
    edit(
        config_dir / "env/example/user_groups.yaml",
        lambda d: d["user_groups"]["early-adopters"].update(teams=["platform"]),
    )
    members = compile_config(config_dir, "example").config["members"]
    assert members["grace@example.test"]["user_groups"] == ["early-adopters"]  # listed and via platform: once
    assert members["ada@example.test"]["user_groups"] == []  # payments is not listed any more
    edit(
        config_dir / "env/example/user_groups.yaml",
        lambda d: d["user_groups"]["early-adopters"].update(teams=["payments"]),
    )
    members = compile_config(config_dir, "example").config["members"]
    assert members["ada@example.test"]["user_groups"] == ["early-adopters"]  # any role of the team


def test_any_control_repository_name_is_accepted_but_not_shared(config_dir, capsys):
    edit(
        config_dir / "env/example/teams/payments.yaml",
        lambda d: d["systems"]["control_repo"].update(repo="example-org/sdlc-control"),
    )
    assert compile_config(config_dir, "example").ok
    edit(
        config_dir / "env/example/teams/platform.yaml",
        lambda d: d.update(systems={"control_repo": {"provider": "github", "repo": "Example-Org/sdlc-control"}}),
    )
    assert main(["validate", "--env", "example", "--dir", str(config_dir)]) == 1
    assert "is also team 'payments''s" in capsys.readouterr().err


def test_a_git_sources_sign_in_needs_a_credential_and_bearer_has_no_username(config_dir, capsys):
    path = config_dir / "env/example/sources/ledger-docs.yaml"
    source = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert source["credential_scheme"] == "bearer" and compile_config(config_dir, "example").ok
    path.write_text(yaml.safe_dump(source | {"credential_username": "svc"}), encoding="utf-8")
    assert main(["validate", "--env", "example", "--dir", str(config_dir)]) == 1
    assert "ledger-docs: a bearer credential has no username" in capsys.readouterr().err
    bare = {k: v for k, v in source.items() if k != "credential"}
    path.write_text(yaml.safe_dump(bare), encoding="utf-8")
    assert main(["validate", "--env", "example", "--dir", str(config_dir)]) == 1
    assert "ledger-docs: credential_scheme without a credential" in capsys.readouterr().err


def test_the_system_identity_and_subscriptions_compile(config_dir, capsys):
    config = compile_config(config_dir, "example").config
    assert config["system"]["teams"] == ["payments"] and config["system"]["machine_users"] == {
        "github": "example-sdlc-bot"
    }
    plan = config["subscriptions"]["ci_plan"]
    assert plan["enabled"] is True and plan["agent"] == "ci_workflow_agent" and plan["filters"]["merged"] is True
    assert config["team_systems"]["payments"]["repositories"][0]["workspace"]["test"] == ["pytest -q"]
    assert config["surfaces"]["event_agents"]["system"] is True
    (config_dir / "env/example/system.yaml").unlink()  # no system identity: no unattended runs, one warning
    assert main(["validate", "--env", "example", "--dir", str(config_dir)]) == 0
    err = capsys.readouterr().err
    assert "no event starts an unattended run" in err and "ci_write" not in err
