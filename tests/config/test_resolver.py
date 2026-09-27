"""Stage 3b: identities -> EffectivePolicy (teams, roles, tools, denies, argument limits)."""

import pytest
import yaml
from sdlc_config import PolicyCache, load_snapshot, resolve

from tests.support.entra import TEST_ENV

VIEWER_TOOLS = {
    "ping",
    "whoami",
    "list_skills",
    "load_skill",
    "get_agent_context",
    "search_knowledge",
}
DEV_TOOLS = VIEWER_TOOLS | {"graph_query", "generate_tests", "review_code"}
PAYMENTS_REPOS = {"payments-api", "payments-ui"}
PLATFORM_REPOS = {"platform-infra", "platform-ci"}


@pytest.fixture
def snap(config_dir):
    return load_snapshot(config_dir, "local", TEST_ENV)


def edit_yaml(path, mutate):
    doc = yaml.safe_load(path.read_text())
    mutate(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def test_no_identities_means_nothing(snap):
    policy = resolve(snap, [])
    assert policy.tools == {} and policy.roles == {} and policy.teams == {}


def test_eng_all_is_viewer_only(snap):
    policy = resolve(snap, ["eng-all"])
    assert set(policy.tools) == VIEWER_TOOLS
    assert policy.roles["viewer"] == ("roles.yaml#bindings[0]",)
    assert not policy.allows("review_code")


def test_payments_developer(snap):
    policy = resolve(snap, ["eng-all", "payments-devs"])
    assert set(policy.teams) == {"payments"}
    assert set(policy.tools) == DEV_TOOLS
    review = policy.tools["review_code"]
    assert review.constraints == {"repo": PAYMENTS_REPOS}
    assert review.constraint_sources == (
        "teams/payments.yaml#policy/tools/constraints/review_code",
    )
    assert review.allowed_by == ("role:developer <- teams/payments.yaml#membership[0]",)
    # viewer comes both from the global binding and by inheritance from developer
    assert set(policy.roles["viewer"]) == {
        "roles.yaml#bindings[0]",
        "inherited from role:developer",
    }
    assert "approve_design" not in policy.tools


def test_payments_lead_gets_approve_design_within_payments(snap):
    policy = resolve(snap, ["eng-all", "payments-leads"])
    assert policy.tools["approve_design"].constraints == {"repo": PAYMENTS_REPOS}
    assert {"lead", "developer", "viewer"} <= set(policy.roles)


def test_platform_developer_gets_platform_repos(snap):
    policy = resolve(snap, ["eng-all", "platform-devs"])
    assert policy.tools["review_code"].constraints == {"repo": PLATFORM_REPOS}
    assert set(policy.teams) == {"platform"}


def test_member_of_two_teams_gets_union_of_limits(snap):
    policy = resolve(snap, ["payments-devs", "platform-devs"])
    assert policy.tools["review_code"].constraints == {"repo": PAYMENTS_REPOS | PLATFORM_REPOS}
    assert len(policy.tools["review_code"].constraint_sources) == 2


def test_admin_gets_whole_catalog_unconstrained(snap):
    policy = resolve(snap, ["eng-all", "platform-admins", "payments-devs"])
    assert set(policy.tools) == set(snap.tools)  # "*" = every catalog tool
    assert policy.tools["review_code"].constraints is None  # admin is unconstrained
    assert policy.allows("config_explain") and policy.allows("config_info")


def test_unknown_aliases_are_ignored(snap):
    assert resolve(snap, ["not-a-group"]).tools == {}


def test_team_deny_wins_over_role_allow(config_dir):
    edit_yaml(
        config_dir / "teams/payments.yaml",
        lambda d: d["policy"]["tools"].update(deny=["review_code"]),
    )
    snap = load_snapshot(config_dir, "local", TEST_ENV)
    policy = resolve(snap, ["payments-devs"])
    assert "review_code" not in policy.tools
    assert policy.denied["review_code"] == ("teams/payments.yaml#policy/tools/deny",)
    # the deny belongs to the payments team: platform developers keep the tool
    assert resolve(snap, ["platform-devs"]).allows("review_code")


def test_role_deny_wins_even_over_admin_wildcard(config_dir):
    edit_yaml(
        config_dir / "roles.yaml",
        lambda d: d["roles"]["viewer"]["tools"].update(deny=["approve_design"]),
    )
    snap = load_snapshot(config_dir, "local", TEST_ENV)
    policy = resolve(snap, ["eng-all", "platform-admins"])
    assert "approve_design" not in policy.tools
    assert policy.denied["approve_design"] == ("role:viewer deny",)


def test_app_role_identities(config_dir):
    edit_yaml(
        config_dir / "teams/payments.yaml",
        lambda d: d["membership"].append(
            {"app_role": "SDLC.Payments.Developer", "roles": ["developer"]}
        ),
    )
    snap = load_snapshot(config_dir, "local", TEST_ENV)
    policy = resolve(snap, [], app_roles=["SDLC.Payments.Developer"])
    assert set(policy.teams) == {"payments"}
    assert policy.tools["review_code"].constraints == {"repo": PAYMENTS_REPOS}


def test_explain_is_json_friendly(snap):
    import json

    view = resolve(snap, ["eng-all", "payments-devs"]).explain()
    assert json.loads(json.dumps(view))["tools"]["review_code"]["constraints"] == {
        "repo": sorted(PAYMENTS_REPOS)
    }


def test_policy_cache_shares_by_identity_and_version(snap, config_dir):
    cache = PolicyCache()
    a = cache.get(snap, ["payments-devs", "eng-all"])
    assert cache.get(snap, ["eng-all", "payments-devs"]) is a  # order does not matter
    assert cache.get(snap, ["eng-all"]) is not a
    (config_dir / "tools.yaml").write_text((config_dir / "tools.yaml").read_text() + "\n# v2\n")
    newer = load_snapshot(config_dir, "local", TEST_ENV)
    b = cache.get(newer, ["payments-devs", "eng-all"])
    assert b is not a and b.config_version == newer.version
