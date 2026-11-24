from sdlc_directory import memberships

CONFIG = {
    "teams": {"payments": {"roles": ["member", "lead"]}, "search": {"roles": ["member"]}},
    "user_groups": {"early-adopters": {}},
    "members": {
        "ada@example.test": {"teams": {"payments": ["member", "lead"]}, "user_groups": []},
        "grace@example.test": {"teams": {"search": ["member"]}, "user_groups": ["early-adopters"]},
        "old@example.test": {"teams": {"retired": ["member"], "search": ["lead"]}, "user_groups": ["gone"]},
    },
}


def test_team_roles_and_user_groups_from_configuration():
    ada = memberships(CONFIG, "Ada@example.test")
    assert dict(ada.teams) == {"payments": frozenset({"member", "lead"})} and ada.user_groups == frozenset()
    grace = memberships(CONFIG, "grace@example.test")
    assert dict(grace.teams) == {"search": frozenset({"member"})} and grace.user_groups == {"early-adopters"}


def test_unlisted_user_has_no_teams():
    nobody = memberships(CONFIG, "isha@example.test")
    assert dict(nobody.teams) == {} and nobody.user_groups == frozenset()


def test_undeclared_teams_roles_and_groups_count_for_nothing():
    old = memberships(CONFIG, "old@example.test")
    assert dict(old.teams) == {} and old.user_groups == frozenset()
