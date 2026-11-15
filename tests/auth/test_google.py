"""The GCP stack's Google ID token verifier, principal and adapter (CH-0021, NFR-SEC-003)."""

import time
from types import SimpleNamespace

import pytest
from fastmcp.server.auth.providers.jwt import RSAKeyPair
from sdlc_auth.google import (
    GOOGLE_ISSUER,
    GoogleAdapter,
    google_verifier_from_env,
    principal_from_google_claims,
)
from sdlc_auth.groups import StaticGroups
from sdlc_config import load_snapshot, resolve

from tests.support.config import GOOGLE_DOMAIN, group_for
from tests.support.entra import TEST_ENV, FakeEntra
from tests.support.google import OTHER_CLIENT_ID, FakeGoogle

SUB = "112233445566778899001"
EMAIL = f"dev@{GOOGLE_DOMAIN}"


@pytest.fixture
def google() -> FakeGoogle:
    return FakeGoogle()


async def test_valid_token_yields_principal(google):
    access = await google.verifier().load_access_token(google.token(sub=SUB, email=EMAIL))
    assert access is not None
    p = principal_from_google_claims(access.claims)
    assert (p.user_id, p.upn, p.tid, p.provider) == (SUB, EMAIL, GOOGLE_DOMAIN, "google")
    assert p.app_roles == frozenset() and p.scopes == ()


@pytest.mark.parametrize(
    ("case", "kwargs"),
    [
        ("expired", {"expires_in": -30}),
        ("another client's token", {"audience": OTHER_CLIENT_ID}),
        ("wrong issuer", {"issuer": "https://issuer.example.test"}),
        ("unverified email", {"email_verified": False}),
        ("email_verified as a string", {"email_verified": "true"}),
        ("consumer account (no hd)", {"omit": ["hd"]}),
        ("another organisation", {"hd": "elsewhere.test"}),
        ("no email", {"omit": ["email"]}),
        ("signed by another key", {"key": RSAKeyPair.generate()}),
    ],
)
async def test_refused_tokens(google, case, kwargs):
    assert await google.verifier().load_access_token(google.token(**kwargs)) is None, case


async def test_an_entra_token_is_refused():
    """Each stack refuses the other's token (FR-IDN-001): issuer, audience and key all differ."""
    google, entra = FakeGoogle(), FakeEntra()
    assert await google.verifier().load_access_token(entra.token()) is None
    assert await entra.verifier().load_access_token(google.token()) is None


async def test_domains_are_case_insensitive(google):
    token = google.token(hd=GOOGLE_DOMAIN.upper())
    assert await google.verifier().load_access_token(token) is not None


async def test_a_blocked_sub_is_refused(google):
    verifier = google.verifier(blocked_reason=lambda sub: "left" if sub == SUB else None)
    assert await verifier.load_access_token(google.token(sub=SUB)) is None
    assert await verifier.load_access_token(google.token()) is not None


def test_principal_needs_a_google_token():
    with pytest.raises(ValueError):
        principal_from_google_claims({"sub": SUB, "email": EMAIL, "iss": "https://x.test"})
    with pytest.raises(ValueError):
        principal_from_google_claims({"oid": "x", "tid": "y"})  # an Entra claim set


def test_verifier_from_env_fails_closed(monkeypatch):
    monkeypatch.delenv("SDLC_OAUTH_CLIENT_IDS", raising=False)
    monkeypatch.setenv("SDLC_ALLOWED_DOMAINS", GOOGLE_DOMAIN)
    with pytest.raises(SystemExit):
        google_verifier_from_env()
    monkeypatch.setenv("SDLC_OAUTH_CLIENT_IDS", " a.apps.googleusercontent.com , b ")
    monkeypatch.setenv("SDLC_ALLOWED_DOMAINS", "")
    with pytest.raises(SystemExit):
        google_verifier_from_env()
    monkeypatch.setenv("SDLC_ALLOWED_DOMAINS", f"{GOOGLE_DOMAIN.upper()},other.test")
    verifier = google_verifier_from_env()
    assert verifier.allowed_domains == (GOOGLE_DOMAIN, "other.test")


# --- GoogleAdapter ------------------------------------------------------------------------


@pytest.fixture(scope="module")
def snap(tmp_path_factory):
    from tests.support.config import make_config_dir

    return load_snapshot(make_config_dir(tmp_path_factory.mktemp("cfg")), "local", TEST_ENV)


def _adapter(groups: dict[str, list[str]]) -> GoogleAdapter:
    return GoogleAdapter(StaticGroups(groups), audience=[FakeGoogle().audience])


def _principal(email: str = EMAIL):
    claims = {"sub": SUB, "email": email, "hd": GOOGLE_DOMAIN, "iss": GOOGLE_ISSUER}
    return principal_from_google_claims(claims)


async def test_adapter_memberships_are_configured_groups_only(snap):
    member, admin = group_for("SDLC.Payments.Member"), group_for("SDLC.Admin")
    adapter = _adapter({EMAIL: [member, "not-in-config@example.test"]})
    keys = await adapter.memberships(_principal(), snap)
    assert keys == frozenset({f"group:{member}"})
    assert f"group:{admin}" not in keys


async def test_adapter_users_yaml_by_verified_email(snap):
    adapter = _adapter({})
    assert adapter.user_alias(_principal("Direct.Dev@example.com"), snap.users) == "direct-dev"
    assert adapter.user_alias(_principal(), snap.users) is None


async def test_adapter_policy_matches_the_entra_persona(snap):
    """The adapter's keys resolve exactly as the Entra stack's app roles do."""
    from sdlc_config import split_memberships

    groups = [group_for("SDLC.User"), group_for("SDLC.Payments.Approver")]
    keys = await _adapter({EMAIL: groups}).memberships(_principal(), snap)
    app_roles, group_emails = split_memberships(keys)
    google = resolve(snap, app_roles, None, group_emails)
    entra = resolve(snap, ["SDLC.User", "SDLC.Payments.Approver"])
    assert app_roles == () and set(google.roles) == set(entra.roles)


def test_adapter_describe_has_no_entra_fields():
    view = _adapter({}).describe(_principal())
    assert view == {
        "provider": "google",
        "sub": SUB,
        "email": EMAIL,
        "name": None,
        "domain": GOOGLE_DOMAIN,
    }


@pytest.mark.parametrize(
    ("claims", "reason"),
    [
        ({"exp": time.time() - 60, "iss": GOOGLE_ISSUER}, "expired"),
        ({"iss": "https://login.microsoftonline.com/t/v2.0"}, "wrong_issuer"),
        ({"iss": GOOGLE_ISSUER, "aud": OTHER_CLIENT_ID}, "wrong_audience"),
        (
            {"iss": GOOGLE_ISSUER, "aud": FakeGoogle().audience, "email_verified": False},
            "unverified_email",
        ),
        (
            {
                "iss": GOOGLE_ISSUER,
                "aud": FakeGoogle().audience,
                "email_verified": True,
                "hd": "elsewhere.test",
            },
            "wrong_domain",
        ),
        (
            {
                "iss": GOOGLE_ISSUER,
                "aud": FakeGoogle().audience,
                "email_verified": True,
                "hd": GOOGLE_DOMAIN,
            },
            "invalid_token",
        ),
    ],
)
def test_adapter_rejection_reasons(claims, reason):
    snapshot = SimpleNamespace(
        platform=SimpleNamespace(google=SimpleNamespace(allowed_domains=(GOOGLE_DOMAIN,)))
    )
    got, claimed = _adapter({}).rejection({"sub": SUB, **claims}, snapshot)
    assert got == reason and claimed["sub"] == SUB
