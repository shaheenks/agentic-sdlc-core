"""Google Groups lookup for the GCP stack (CH-0021, design N10; FR-IDN-004).

The Cloud Identity Groups API is faked with httpx.MockTransport: no network, no credentials.
"""

import logging

import httpx
import pytest
from sdlc_auth.groups import DIRECT, TRANSITIVE, CloudIdentityGroups, StaticGroups

USER = "dev@example.test"
PAYMENTS = "sdlc-payments-member@example.test"
ADMIN = "sdlc-admin@example.test"
MISSING = "sdlc-missing@example.test"


class FakeGroupsApi:
    """groups:lookup, memberships:lookup and searchTransitiveGroups over a fixed directory."""

    def __init__(self, members: dict[str, set[str]], transitive: dict[str, set[str]] | None = None):
        self.members = members  # group email -> member emails (direct)
        self.transitive = transitive or {}  # user email -> every group, nested ones included
        self.calls: list[str] = []
        self.fail: int | None = None  # answer every call with this status
        self.page_size = 1

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer fake-token"
        path, params = request.url.path, request.url.params
        self.calls.append(path.rsplit("/", 1)[-1])
        if self.fail:
            return httpx.Response(self.fail, json={"error": {"code": self.fail}})
        if path.endswith("/groups:lookup"):
            group = params["groupKey.id"]
            if group not in self.members:
                return httpx.Response(404, json={})
            return httpx.Response(200, json={"name": f"groups/id-{group.split('@')[0]}"})
        if path.endswith("/memberships:lookup"):
            group = next(g for g in self.members if f"id-{g.split('@')[0]}" in path)
            if params["memberKey.id"] in self.members[group]:
                return httpx.Response(200, json={"name": f"{path}/m1"})
            return httpx.Response(404, json={})
        if path.endswith("/memberships:searchTransitiveGroups"):
            user = params["query"].split("'")[1]
            groups = sorted(self.transitive.get(user, set()))
            start = int(params.get("pageToken") or 0)
            page = groups[start : start + self.page_size]
            body = {"memberships": [{"groupKey": {"id": g}} for g in page]}
            if start + self.page_size < len(groups):
                body["nextPageToken"] = str(start + self.page_size)
            return httpx.Response(200, json=body)
        return httpx.Response(400)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def fake_token() -> str:
    return "fake-token"


def directory(api: FakeGroupsApi, mode=DIRECT, cache_seconds=300, clock=None):
    client = httpx.AsyncClient(transport=httpx.MockTransport(api.handler))
    return CloudIdentityGroups(
        mode=mode,
        cache_seconds=cache_seconds,
        token=fake_token,
        client=client,
        clock=clock or Clock(),
    )


async def test_direct_mode_checks_each_configured_group():
    api = FakeGroupsApi({PAYMENTS: {USER}, ADMIN: {"someone@example.test"}})
    groups = await directory(api).groups_of(USER.upper(), [PAYMENTS, ADMIN, MISSING])
    assert groups == {PAYMENTS}
    assert api.calls.count("memberships:lookup") == 2  # MISSING has no group to ask about


async def test_direct_mode_does_not_follow_nested_groups():
    """Cloud Identity Free: membership through a nested group does not count."""
    nested = "sdlc-nested@example.test"
    api = FakeGroupsApi({PAYMENTS: {nested}, nested: {USER}})
    assert await directory(api).groups_of(USER, [PAYMENTS]) == frozenset()


async def test_transitive_mode_pages_and_keeps_only_configured_groups():
    api = FakeGroupsApi({}, transitive={USER: {PAYMENTS, ADMIN, "other@example.test"}})
    groups = await directory(api, mode=TRANSITIVE).groups_of(USER, [PAYMENTS, ADMIN])
    assert groups == {PAYMENTS, ADMIN}
    assert api.calls.count("memberships:searchTransitiveGroups") == 3  # one group per page


async def test_answers_are_cached_until_they_expire():
    """FR-IDN-004: removing a user from a group takes effect within the cache time."""
    clock = Clock()
    api = FakeGroupsApi({PAYMENTS: {USER}})
    groups = directory(api, cache_seconds=60, clock=clock)
    assert await groups.groups_of(USER, [PAYMENTS]) == {PAYMENTS}
    api.members[PAYMENTS] = set()  # removed in Cloud Identity
    clock.now += 59
    assert await groups.groups_of(USER, [PAYMENTS]) == {PAYMENTS}  # still cached
    clock.now += 2
    assert await groups.groups_of(USER, [PAYMENTS]) == frozenset()


async def test_a_config_change_is_not_served_from_the_cache():
    api = FakeGroupsApi({PAYMENTS: {USER}, ADMIN: {USER}})
    groups = directory(api)
    assert await groups.groups_of(USER, [PAYMENTS]) == {PAYMENTS}
    assert await groups.groups_of(USER, [PAYMENTS, ADMIN]) == {PAYMENTS, ADMIN}


@pytest.mark.parametrize("mode", [DIRECT, TRANSITIVE])
@pytest.mark.parametrize("status", [403, 429, 500])
async def test_a_failed_lookup_gives_no_groups_and_is_not_cached(mode, status, caplog):
    api = FakeGroupsApi({PAYMENTS: {USER}}, transitive={USER: {PAYMENTS}})
    groups = directory(api, mode=mode)
    api.fail = status
    with caplog.at_level(logging.WARNING, logger="sdlc.auth.groups"):
        assert await groups.groups_of(USER, [PAYMENTS]) == frozenset()
    assert str(status) in caplog.text and USER not in caplog.text  # never the user's email
    api.fail = None
    assert await groups.groups_of(USER, [PAYMENTS]) == {PAYMENTS}


async def test_a_network_error_gives_no_groups():
    def boom(request):
        raise httpx.ConnectError("down", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(boom))
    groups = CloudIdentityGroups(token=fake_token, client=client)
    assert await groups.groups_of(USER, [PAYMENTS]) == frozenset()


async def test_an_email_with_a_quote_is_refused_in_transitive_mode():
    api = FakeGroupsApi({}, transitive={})
    groups = directory(api, mode=TRANSITIVE)
    assert await groups.groups_of("a'b@example.test", [PAYMENTS]) == frozenset()
    assert api.calls == []


async def test_nothing_is_asked_without_configured_groups():
    api = FakeGroupsApi({PAYMENTS: {USER}})
    assert await directory(api).groups_of(USER, []) == frozenset()
    assert api.calls == []


def test_unknown_mode_is_refused():
    with pytest.raises(ValueError):
        CloudIdentityGroups(mode="nested", token=fake_token)


async def test_static_groups_answer_only_candidates():
    static = StaticGroups({USER.upper(): [PAYMENTS, ADMIN]})
    assert await static.groups_of(USER, [PAYMENTS]) == {PAYMENTS}
