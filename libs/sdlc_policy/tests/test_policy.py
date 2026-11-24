import pytest
from sdlc_directory import Memberships
from sdlc_policy import DEFAULT_DENY, NotATeamMember, RateLimiter, effective_policy

CONFIG = {
    "tool_groups": {
        "identity": {"tools": ["whoami"]},
        "artifacts": {"tools": ["artifact_list", "artifact_save"]},
        "release": {"tools": ["release_cut"]},
        "experiments": {"tools": ["try_new_thing"]},
        "orphan": {"tools": ["never_granted"]},
    },
    "surfaces": {
        "sdlc_ui": {"tool_groups": ["identity", "artifacts", "release", "experiments", "orphan"]},
        "gemini_enterprise": {"tool_groups": ["identity"]},
    },
    "grants": [
        {"id": "basics", "tool_groups": ["identity", "artifacts"], "to": {"everyone": True}},
        {"id": "payments-leads-release", "tool_groups": ["release"], "to": {"teams": ["payments:lead"]}},
        {"id": "early", "tool_groups": ["experiments"], "to": {"user_groups": ["early-adopters"]}},
    ],
    "rate_limits": {
        "tool_calls": {
            "per_user_per_minute": 2,
            "per_team_per_minute": 3,
            "overrides": [{"id": "early", "to": {"user_groups": ["early-adopters"]}, "per_user_per_minute": 5}],
        }
    },
}
LEAD = Memberships({"payments": frozenset({"member", "lead"})}, frozenset({"early-adopters"}))
MEMBER = Memberships({"payments": frozenset({"member"})})
NOBODY = Memberships()


def policy(memberships, surface="sdlc_ui", team=None):
    return effective_policy(CONFIG, "v1", surface, memberships, team)


def test_everyone_gets_the_basics_and_nothing_ungranted():
    p = policy(NOBODY)
    assert set(p.tools) == {"whoami", "artifact_list", "artifact_save"}
    denied = p.authorize("never_granted")
    assert not denied.allowed and denied.rule == DEFAULT_DENY


def test_team_role_and_user_group_grants():
    assert "release_cut" in policy(LEAD).tools
    assert "release_cut" not in policy(MEMBER).tools
    assert "try_new_thing" in policy(LEAD).tools


def test_decision_names_the_rule():
    decision = policy(LEAD).authorize("release_cut")
    assert decision.allowed
    assert decision.rule == "grant:payments-leads-release/tool_group:release/surface:sdlc_ui"


def test_surface_narrows_what_the_user_may_use():
    p = policy(LEAD, surface="gemini_enterprise")
    assert set(p.tools) == {"whoami"}
    assert not p.authorize("artifact_save").allowed


def test_undeclared_surface_gets_nothing():
    assert policy(LEAD, surface="unknown").tools == {}


def test_team_run_is_the_intersection_with_the_teams_grants():
    p = policy(LEAD, team="payments")
    assert "release_cut" in p.tools  # granted to the team (its lead role) and to the starter
    assert "try_new_thing" not in p.tools  # the starter's own user-group grant does not reach the team run
    assert "whoami" in p.tools  # everyone's grant


def test_team_run_for_a_team_the_user_is_not_in():
    with pytest.raises(NotATeamMember):
        policy(NOBODY, team="payments")


def test_rate_limit_per_user_with_overrides():
    now = [0.0]
    limiter = RateLimiter(clock=lambda: now[0])
    assert [limiter.check(CONFIG, "u1", MEMBER, None).allowed for _ in range(3)] == [True, True, False]
    refused = limiter.check(CONFIG, "u1", MEMBER, None)
    assert refused.reason == "rate_limited" and refused.rule == "rate_limits.tool_calls"
    assert sum(limiter.check(CONFIG, "u2", LEAD, None).allowed for _ in range(6)) == 5
    now[0] = 61
    assert limiter.check(CONFIG, "u1", MEMBER, None).allowed


def test_rate_limit_per_team():
    limiter = RateLimiter(clock=lambda: 0.0)
    results = [limiter.check(CONFIG, f"user{i}", MEMBER, "payments").allowed for i in range(4)]
    assert results == [True, True, True, False]
