import json

import httpx
import pytest
from fastmcp.server.auth.providers.jwt import RSAKeyPair
from sdlc_auth import GraphGroupResolver, effective_group_ids, principal_from_claims

from tests.support.entra import G_PAYMENTS_DEVS, TENANT

OID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


async def test_valid_token_yields_principal(entra):
    access = await entra.verifier().load_access_token(
        entra.token(oid=OID, groups=[G_PAYMENTS_DEVS.upper()], upn="dev@corp.test")
    )
    assert access is not None
    p = principal_from_claims(access.claims)
    assert (p.oid, p.tid, p.upn) == (OID, TENANT, "dev@corp.test")
    assert p.group_ids == {G_PAYMENTS_DEVS}  # normalized to lower case
    assert p.scopes == ("access_as_user",)
    assert not p.groups_overage


async def test_v1_style_audience_accepted(entra):
    assert await entra.verifier().load_access_token(entra.token(audience=f"api://{entra.audience}"))


@pytest.mark.parametrize(
    ("case", "kwargs"),
    [
        ("expired", {"expires_in": -30}),
        ("wrong audience", {"audience": "api://someone-else"}),
        ("wrong issuer", {"issuer": "https://login.microsoftonline.com/other/v2.0"}),
        ("wrong tenant id", {"tid": "99999999-9999-9999-9999-999999999999"}),
        ("no oid", {"omit": ["oid"]}),
        ("app-only token (no scp)", {"omit": ["scp"], "roles": ["Tools.Call"]}),
        ("app-only token (idtyp)", {"idtyp": "app"}),
        ("missing required scope", {"scp": "User.Read"}),
    ],
)
async def test_invalid_tokens_rejected(entra, case, kwargs):
    assert await entra.verifier().load_access_token(entra.token(**kwargs)) is None, case


async def test_token_signed_by_other_key_rejected(entra):
    forged = entra.token(key=RSAKeyPair.generate())
    assert await entra.verifier().load_access_token(forged) is None


async def test_garbage_token_rejected(entra):
    assert await entra.verifier().load_access_token("not.a.jwt") is None


def test_overage_detected():
    p = principal_from_claims(
        {
            "oid": OID,
            "tid": TENANT,
            "scp": "access_as_user",
            "_claim_names": {"groups": "src1"},
            "_claim_sources": {"src1": {}},
        }
    )
    assert p.groups_overage and p.group_ids == frozenset()


class _StubResolver:
    async def resolve(self, principal):
        return frozenset({G_PAYMENTS_DEVS})


async def test_effective_group_ids_sources():
    base = {"oid": OID, "tid": TENANT, "scp": "access_as_user"}
    normal = principal_from_claims({**base, "groups": [G_PAYMENTS_DEVS]})
    overage = principal_from_claims({**base, "hasgroups": True})
    assert await effective_group_ids(normal, None) == ({G_PAYMENTS_DEVS}, "token")
    assert await effective_group_ids(overage, None) == (frozenset(), "overage_unresolved")
    assert await effective_group_ids(overage, _StubResolver()) == ({G_PAYMENTS_DEVS}, "graph")


async def test_graph_resolver_pages_and_caches():
    calls = {"token": 0, "graph": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth2/v2.0/token"):
            calls["token"] += 1
            assert b"grant_type=client_credentials" in request.content
            return httpx.Response(200, json={"access_token": "app-tok", "expires_in": 3600})
        calls["graph"] += 1
        assert request.headers["Authorization"] == "Bearer app-tok"
        if "skiptoken" not in str(request.url):
            assert f"/users/{OID}/transitiveMemberOf/" in request.url.path
            return httpx.Response(
                200,
                json={
                    "value": [{"id": G_PAYMENTS_DEVS.upper()}],
                    "@odata.nextLink": "https://graph.test/v1.0/next?$skiptoken=2",
                },
            )
        return httpx.Response(200, json={"value": [{"id": "abc00000-0000-0000-0000-000000000000"}]})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    resolver = GraphGroupResolver(
        TENANT, "client", "secret", http=http, graph_base="https://graph.test/v1.0"
    )
    principal = principal_from_claims({"oid": OID, "tid": TENANT, "hasgroups": True})
    first = await resolver.resolve(principal)
    assert first == {G_PAYMENTS_DEVS, "abc00000-0000-0000-0000-000000000000"}
    assert await resolver.resolve(principal) == first  # cached
    assert calls == {"token": 1, "graph": 2}


async def test_graph_resolver_rejects_non_guid_oid():
    resolver = GraphGroupResolver(TENANT, "c", "s", http=httpx.AsyncClient())
    bad = principal_from_claims({"oid": "../../me", "tid": TENANT, "hasgroups": True})
    with pytest.raises(ValueError):
        await resolver.resolve(bad)


def test_principal_requires_oid_and_tid():
    with pytest.raises(ValueError):
        principal_from_claims(json.loads('{"tid": "x"}'))
