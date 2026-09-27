"""Stage 3c: sdlc_policy.authorize / visible_tools (pure decisions)."""

import pytest
from sdlc_config import load_snapshot, resolve
from sdlc_policy import DEFAULT_DENY, authorize, visible_tools

from tests.support.entra import TEST_ENV


@pytest.fixture
def snap(config_dir):
    return load_snapshot(config_dir, "local", TEST_ENV)


def test_default_deny_for_ungranted_tool(snap):
    decision = authorize(resolve(snap, ["eng-all"]), "review_code", {"repo": "payments-api"})
    assert not decision.allowed and decision.matched_rule == DEFAULT_DENY


def test_unknown_tool_is_denied(snap):
    assert not authorize(resolve(snap, ["eng-all"]), "rm_rf", {}).allowed


def test_allowed_without_limits_names_granting_rule(snap):
    decision = authorize(resolve(snap, ["eng-all"]), "list_skills", {})
    assert decision.allowed
    assert decision.matched_rule == "role:viewer <- roles.yaml#bindings[1]"


@pytest.mark.parametrize(
    ("args", "allowed", "reason_part"),
    [
        ({"repo": "payments-api"}, True, "within argument limits"),
        ({"repo": "payments-ui", "ref": "dev"}, True, "within argument limits"),
        ({"repo": "platform-infra"}, False, "repo='platform-infra' is not allowed"),
        ({}, False, "argument 'repo' is required by policy"),
        ({"repo": ["payments-api"]}, False, "is not allowed"),  # wrong type
        (None, False, "argument 'repo' is required"),
    ],
)
def test_argument_limits(snap, args, allowed, reason_part):
    decision = authorize(resolve(snap, ["payments-devs"]), "review_code", args)
    assert decision.allowed is allowed
    assert reason_part in decision.reason
    assert "teams/payments.yaml#policy/tools/constraints/review_code" in decision.matched_rule


def test_admin_is_not_limited(snap):
    policy = resolve(snap, ["platform-admins", "payments-devs"])
    assert authorize(policy, "review_code", {"repo": "anything"}).allowed
    assert authorize(policy, "config_explain", {"groups": []}).allowed


def test_deny_wins_and_names_the_deny_rule(config_dir):
    teams = config_dir / "teams/payments.yaml"
    teams.write_text(teams.read_text().replace("deny: []", "deny: [generate_tests]"))
    snap = load_snapshot(config_dir, "local", TEST_ENV)
    decision = authorize(
        resolve(snap, ["payments-devs"]), "generate_tests", {"repo": "payments-api"}
    )
    assert not decision.allowed
    assert decision.matched_rule == "teams/payments.yaml#policy/tools/deny"


def test_visible_tools(snap):
    registered = ["ping", "whoami", "review_code", "config_info", "not_in_catalog"]
    assert visible_tools(resolve(snap, ["eng-all"]), registered) == ["ping", "whoami"]
    assert visible_tools(resolve(snap, ["platform-admins"]), registered) == registered[:4]
