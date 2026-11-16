"""sdlc-config check-groups (CH-0026): every configured Google group resolves before a rollout.

The Cloud Identity Groups API is faked with httpx.MockTransport: no network, no credentials.
"""

from types import SimpleNamespace

import httpx
from sdlc_auth.groups import CloudIdentityGroups
from sdlc_config.cli import _check_groups

FOUND = "sdlc-user@example.test"
TYPO = "sdlc-platfrom-member@example.test"


def directory(statuses: dict[str, int]) -> CloudIdentityGroups:
    def handler(request: httpx.Request) -> httpx.Response:
        group = request.url.params["groupKey.id"]
        status = statuses.get(group, 404)
        body = {"name": f"groups/id-{group.split('@')[0]}"} if status == 200 else {}
        return httpx.Response(status, json=body)

    async def token() -> str:
        return "fake-token"

    return CloudIdentityGroups(
        token=token, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )


def snap(*groups: str):
    return SimpleNamespace(env="dev", group_values=frozenset(groups))


def test_all_groups_resolve(capsys):
    assert _check_groups(snap(FOUND), directory({FOUND: 200})) == 0
    out = capsys.readouterr().out
    assert f"group: {FOUND} ok" in out and "1/1 resolve" in out


def test_an_unresolvable_group_fails_and_is_named(capsys):
    assert _check_groups(snap(FOUND, TYPO), directory({FOUND: 200, TYPO: 403})) == 1
    out = capsys.readouterr().out
    assert f"group: {TYPO} NOT RESOLVED" in out and "403" in out
    assert "1/2 resolve" in out


def test_no_groups_in_config(capsys):
    assert _check_groups(snap(), directory({})) == 0
    assert "no group bindings" in capsys.readouterr().out
