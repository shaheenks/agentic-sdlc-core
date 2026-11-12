import json

import pytest
from fastmcp.server.auth.providers.jwt import RSAKeyPair
from sdlc_auth import principal_from_claims
from sdlc_auth.entra import entra_issuer, entra_jwks_uri

from tests.support.entra import G_PAYMENTS_DEVS, TENANT

OID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


async def test_valid_token_yields_principal(entra):
    access = await entra.verifier().load_access_token(
        entra.token(oid=OID, roles=[G_PAYMENTS_DEVS], upn="dev@corp.test")
    )
    assert access is not None
    p = principal_from_claims(access.claims)
    assert (p.oid, p.tid, p.upn) == (OID, TENANT, "dev@corp.test")
    assert p.app_roles == {G_PAYMENTS_DEVS}
    assert p.scopes == ("access_as_user",)


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


def test_groups_claim_is_ignored():
    """CH-0011: membership comes from app roles only; a `groups` claim or overage marker grants
    nothing and changes nothing."""
    base = {"oid": OID, "tid": TENANT, "scp": "access_as_user"}
    with_groups = principal_from_claims(
        {**base, "groups": ["00000000-0000-0000-0000-000000000002"], "hasgroups": True}
    )
    assert with_groups == principal_from_claims(base)
    assert with_groups.app_roles == frozenset()
    assert not hasattr(with_groups, "group_ids")


def test_principal_requires_oid_and_tid():
    with pytest.raises(ValueError):
        principal_from_claims(json.loads('{"tid": "x"}'))


def test_issuer_and_jwks_follow_the_authority_host():
    host = "https://login.microsoftonline.us"
    assert entra_issuer(TENANT, host) == f"{host}/{TENANT}/v2.0"
    assert entra_jwks_uri(TENANT, host) == f"{host}/{TENANT}/discovery/v2.0/keys"
    assert entra_issuer(TENANT).startswith("https://login.microsoftonline.com/")
