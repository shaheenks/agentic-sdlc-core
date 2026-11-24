import asyncio

import httpx
from sdlc_directory import CloudIdentityGroups, Directory

CONFIG = {
    "teams": {
        "payments": {"roles": {"member": ["payments@example.test"], "lead": ["payments-leads@example.test"]}},
        "search": {"roles": {"member": ["search@example.test"]}},
    },
    "user_groups": {"early-adopters": {"groups": ["early@example.test"]}},
    "identity": {"directory": {"mode": "static"}},
    "directory_users": {
        "ada@example.test": ["payments@example.test", "payments-leads@example.test", "unrelated@example.test"],
        "grace@example.test": ["early@example.test"],
    },
}


def memberships(email, config=CONFIG, directory=None):
    return asyncio.run((directory or Directory()).memberships(email, config))


def test_team_roles_and_user_groups_from_static_groups():
    ada = memberships("Ada@example.test")
    assert dict(ada.teams) == {"payments": frozenset({"member", "lead"})}
    assert ada.user_groups == frozenset()
    grace = memberships("grace@example.test")
    assert dict(grace.teams) == {} and grace.user_groups == {"early-adopters"}


def test_user_in_no_mapped_group_has_no_teams():
    nobody = memberships("isha@example.test")
    assert dict(nobody.teams) == {} and nobody.user_groups == frozenset()


def cloud_identity(handler) -> CloudIdentityGroups:
    async def token() -> str:
        return "service-token"

    return CloudIdentityGroups(token=token, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def test_one_failing_group_keeps_the_users_other_groups():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("groups:lookup"):
            group = request.url.params["groupKey.id"]
            if group == "search@example.test":
                return httpx.Response(500)
            return httpx.Response(200, json={"name": f"groups/{group.split('@')[0]}"})
        member_of = {"/v1/groups/payments/memberships:lookup", "/v1/groups/early/memberships:lookup"}
        return httpx.Response(200 if request.url.path in member_of else 404, json={})

    lookup = cloud_identity(handler)
    directory = Directory(cloud_lookup=lambda mode, seconds: lookup)
    config = {**CONFIG, "identity": {"directory": {"mode": "direct"}}}
    ada = memberships("ada@example.test", config, directory)
    assert dict(ada.teams) == {"payments": frozenset({"member"})}
    assert ada.user_groups == {"early-adopters"}


def test_transitive_search_failure_gives_no_groups():
    lookup = cloud_identity(lambda request: httpx.Response(403))
    lookup.mode = "transitive"
    assert asyncio.run(lookup.groups_of("ada@example.test", ["payments@example.test"])) == frozenset()
