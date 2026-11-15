"""Google identity for the GCP stack (CH-0021, design N7 to N10).

The user's token is a Google ID token whose audience is OUR OAuth client. It is verified offline
(fastmcp JWTVerifier on Google's signing keys: signature, exp, iss, aud) and then we require:
  - a `sub` (the stable user id) and an `email` with `email_verified` true;
  - `hd` (the Cloud Identity domain) in the configured allowed domains: a consumer Google account
    or another organisation's account is refused.
An Entra token fails the issuer and signature checks. Membership is NOT in the token: the GCP stack
reads Google Groups from the Cloud Identity Groups API (sdlc_auth.groups) and users.yaml by email.

Needs the `server` extra (fastmcp).
"""

import logging
import os
import time
from collections.abc import Callable, Mapping
from typing import Any

from fastmcp.server.auth import AccessToken
from fastmcp.server.auth.providers.jwt import JWTVerifier

from sdlc_auth.groups import GroupDirectory
from sdlc_auth.principal import Principal

log = logging.getLogger("sdlc.auth")

GOOGLE_ISSUER = "https://accounts.google.com"
GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE = "google"  # Principal.provider


def _domains(values) -> tuple[str, ...]:
    return tuple(d.strip().lower() for d in values if d and d.strip())


class GoogleTokenVerifier(JWTVerifier):
    def __init__(
        self,
        *,
        audience: list[str],
        allowed_domains: list[str],
        public_key: str | bytes | None = None,  # tests only; production uses Google's JWKS
        issuer: str = GOOGLE_ISSUER,
        jwks_uri: str = GOOGLE_JWKS_URI,
        base_url: str | None = None,
        blocked_reason: Callable[[str], str | None] | None = None,  # sub -> reason if blocked
    ):
        if not audience or not _domains(allowed_domains):
            raise ValueError("Google token verifier needs OAuth client IDs and allowed domains")
        self.allowed_domains = _domains(allowed_domains)
        self.blocked_reason = blocked_reason
        super().__init__(
            public_key=public_key,
            jwks_uri=None if public_key else jwks_uri,
            issuer=issuer,
            audience=list(audience),
            algorithm="RS256",
            base_url=base_url,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        access = await super().load_access_token(token)
        if access is None:
            return None
        claims = access.claims
        if not claims.get("sub") or not claims.get("email"):
            log.info("token rejected: no sub or email claim")
            return None
        if claims.get("email_verified") is not True:
            log.info("token rejected: email not verified")
            return None
        if str(claims.get("hd", "")).lower() not in self.allowed_domains:
            log.info("token rejected: domain not allowed (hd=%r)", claims.get("hd"))
            return None
        if self.blocked_reason is not None:
            reason = self.blocked_reason(str(claims["sub"]))
            if reason is not None:
                log.warning("token rejected: user sub=%s is blocked (%s)", claims["sub"], reason)
                return None
        return access


def principal_from_google_claims(claims: Mapping[str, Any]) -> Principal:
    """A Principal from Google ID token claims that have ALREADY been validated. The user id is
    `sub` (kept in `oid`, the provider-neutral `user_id`); `upn` is the verified email and `tid`
    the Cloud Identity domain."""
    sub, email = claims.get("sub"), claims.get("email")
    if not sub or not email or claims.get("iss") != GOOGLE_ISSUER:
        raise ValueError("token has no sub/email or is not a Google ID token")
    return Principal(
        oid=str(sub),
        tid=str(claims.get("hd", "")).lower(),
        upn=str(email).lower(),
        name=claims.get("name"),
        scopes=(),
        provider=GOOGLE,
    )


def google_verifier_from_env(
    blocked_reason: Callable[[str], str | None] | None = None,
) -> GoogleTokenVerifier:
    """The verifier the GCP stack's agent and server read from the environment:
    SDLC_OAUTH_CLIENT_IDS (comma-separated OAuth client IDs: the token audience) and
    SDLC_ALLOWED_DOMAINS (comma-separated Cloud Identity domains). Missing values stop startup:
    fail closed."""
    clients = [c.strip() for c in os.environ.get("SDLC_OAUTH_CLIENT_IDS", "").split(",")]
    domains = os.environ.get("SDLC_ALLOWED_DOMAINS", "").split(",")
    clients = [c for c in clients if c]
    if not clients or not _domains(domains):
        raise SystemExit("SDLC_OAUTH_CLIENT_IDS and SDLC_ALLOWED_DOMAINS must be set (fail closed)")
    return GoogleTokenVerifier(
        audience=clients, allowed_domains=domains, blocked_reason=blocked_reason
    )


class GoogleAdapter:
    """The GCP stack's identity adapter (sdlc_mcp.identity.IdentityAdapter, CH-0020): the user is
    `sub`, memberships are `group:<email>` keys from the group directory (only the groups config
    binds), users.yaml is matched on the verified email. `snapshot` is an sdlc_config Snapshot."""

    name = GOOGLE

    def __init__(self, directory: GroupDirectory, audience: list[str]):
        self.directory = directory
        self.audience = tuple(audience)

    def principal(self, claims: Mapping[str, Any]) -> Principal:
        return principal_from_google_claims(claims)

    async def memberships(self, principal: Principal, snapshot: Any) -> frozenset[str]:
        groups = await self.directory.groups_of(principal.upn or "", snapshot.group_values)
        return frozenset(f"group:{g}" for g in groups)

    def user_alias(self, principal: Principal, users: Any) -> str | None:
        return users.alias_for_email(principal.upn)  # verified email (N9), never the sub

    def describe(self, principal: Principal) -> dict[str, Any]:
        return {
            "provider": GOOGLE,
            "sub": principal.oid,
            "email": principal.upn,
            "name": principal.name,
            "domain": principal.tid,
        }

    def rejection(self, claims: dict[str, Any], snapshot: Any) -> tuple[str, dict[str, Any]]:
        claimed = {
            k: claims.get(k)
            for k in ("sub", "email", "hd", "aud", "exp", "iss")
            if claims.get(k) is not None
        }
        google = snapshot.platform.google
        allowed = google.allowed_domains if google else ()
        exp = claims.get("exp")
        if isinstance(exp, int | float) and exp < time.time():
            reason = "expired"
        elif claims.get("iss") != GOOGLE_ISSUER:
            reason = "wrong_issuer"  # e.g. an Entra token on the GCP stack
        elif claims.get("aud") not in self.audience:
            reason = "wrong_audience"
        elif claims.get("email_verified") is not True:
            reason = "unverified_email"
        elif str(claims.get("hd", "")).lower() not in allowed:
            reason = "wrong_domain"
        else:
            reason = "invalid_token"  # e.g. bad signature, unknown signing key, blocked
        return reason, claimed
