import asyncio

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sdlc_identity import GoogleTokens, IdentitySettings, Rejected, check

NOW = 1_800_000_000
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
CONFIG = {
    "identity": {
        "allowed_domains": ["example.test"],
        "clients": {"sdlc_ui": ["ui-client"], "gemini_enterprise": ["ge-client"]},
    },
    "blocked": [{"email": "blocked@example.test", "reason": "left the company"}],
}
SETTINGS = IdentitySettings.from_config(CONFIG)


def id_token(**overrides) -> str:
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "ui-client",
        "sub": "1001",
        "email": "ada@example.test",
        "email_verified": True,
        "hd": "example.test",
        "exp": NOW + 3600,
        **overrides,
    }
    return jwt.encode(claims, KEY, algorithm="RS256")


def verify_locally(token: str) -> dict:
    return jwt.decode(
        token,
        KEY.public_key(),
        algorithms=["RS256"],
        issuer=["https://accounts.google.com"],
        options={"verify_aud": False, "verify_exp": False},
    )


class Introspection:
    def __init__(self, **info) -> None:
        self.info = {
            "aud": "ge-client",
            "sub": "1002",
            "email": "grace@example.test",
            "email_verified": "true",
            "scope": "openid https://www.googleapis.com/auth/userinfo.email",
            "exp": str(NOW + 600),
            **info,
        }
        self.calls = 0

    async def __call__(self, token: str) -> dict:
        self.calls += 1
        if not token.startswith("ya29."):  # Google answers 400 for a token it does not know
            raise Rejected("invalid_token")
        return self.info


def tokens(introspect=None, clock=lambda: NOW) -> GoogleTokens:
    return GoogleTokens(clock=clock, verify_id_token=verify_locally, introspect=introspect or Introspection())


def identify(token: str, gt: GoogleTokens | None = None, settings=SETTINGS):
    return check(asyncio.run((gt or tokens()).claims(token)), settings)


def test_id_token_of_a_declared_client():
    who = identify(id_token())
    assert (who.user_id, who.email, who.surface, who.domain) == ("1001", "ada@example.test", "sdlc_ui", "example.test")


def test_access_token_by_introspection():
    who = identify("ya29.access")
    assert (who.user_id, who.surface) == ("1002", "gemini_enterprise")


@pytest.mark.parametrize(
    ("token", "reason"),
    [
        (id_token(aud="someone-elses-client"), "undeclared_client"),
        (id_token(hd="other.test", email="eve@other.test"), "wrong_domain"),
        (id_token(email_verified=False), "unverified_email"),
        (id_token(email="blocked@example.test"), "blocked"),
        (id_token(email="agents@proj.iam.gserviceaccount.com", hd=None), "service_account"),
        (id_token(exp=NOW - 1), "expired"),
        (id_token(iss="https://login.microsoftonline.com/x/v2.0"), "invalid_token"),
        ("not-a-token", "invalid_token"),
    ],
)
def test_refusals(token, reason):
    with pytest.raises(Rejected) as exc:
        identify(token)
    assert exc.value.reason == reason


def test_access_token_without_email_scope_is_refused():
    with pytest.raises(Rejected) as exc:
        identify("ya29.x", tokens(Introspection(scope="openid https://www.googleapis.com/auth/cloud-platform")))
    assert exc.value.reason == "missing_scope"


def test_verified_claims_are_cached_for_300_seconds():
    introspect, now = Introspection(), [NOW]
    gt = tokens(introspect, clock=lambda: now[0])
    asyncio.run(gt.claims("ya29.a"))
    now[0] += 299
    asyncio.run(gt.claims("ya29.a"))
    assert introspect.calls == 1
    now[0] += 2
    asyncio.run(gt.claims("ya29.a"))
    assert introspect.calls == 2


def test_cache_ends_when_the_token_expires():
    introspect, now = Introspection(exp=str(NOW + 60)), [NOW]
    gt = tokens(introspect, clock=lambda: now[0])
    asyncio.run(gt.claims("ya29.short"))
    now[0] += 61
    with pytest.raises(Rejected, match="expired"):
        asyncio.run(gt.claims("ya29.short"))


def test_block_list_applies_to_cached_tokens():
    gt = tokens()
    token = id_token()
    identify(token, gt)
    blocked = IdentitySettings.from_config({**CONFIG, "blocked": [{"user_id": "1001"}]})
    with pytest.raises(Rejected, match="blocked"):
        identify(token, gt, blocked)


def test_no_declared_clients_refuses_everyone():
    with pytest.raises(Rejected, match="undeclared_client"):
        identify(id_token(), settings=IdentitySettings.from_config({}))
