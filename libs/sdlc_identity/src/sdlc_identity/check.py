"""The checks that depend on the active configuration, run on every request."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sdlc_identity.tokens import Claims, Rejected

EMAIL_SCOPES = ("email", "https://www.googleapis.com/auth/userinfo.email")
SERVICE_ACCOUNT_DOMAIN = ".gserviceaccount.com"


@dataclass(frozen=True)
class Identity:
    """A verified user. `user_id` is the Google account ID (`sub`), the owner of everything the user has."""

    user_id: str
    email: str
    domain: str
    surface: str
    client_id: str
    expires_at: int


@dataclass(frozen=True)
class IdentitySettings:
    allowed_domains: frozenset[str]
    surfaces_by_client: Mapping[str, str]
    blocked_user_ids: frozenset[str]
    blocked_emails: frozenset[str]

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "IdentitySettings":
        """From a compiled bundle: `identity.allowed_domains`, `identity.clients` ({surface: [client IDs]}) and
        `blocked` ([{user_id | email, reason}])."""
        identity = config.get("identity") or {}
        by_client = {cid: surface for surface, ids in (identity.get("clients") or {}).items() for cid in ids}
        blocked = config.get("blocked") or []
        return cls(
            allowed_domains=frozenset(d.lower() for d in identity.get("allowed_domains") or ()),
            surfaces_by_client=by_client,
            blocked_user_ids=frozenset(str(b["user_id"]) for b in blocked if b.get("user_id")),
            blocked_emails=frozenset(str(b["email"]).lower() for b in blocked if b.get("email")),
        )


def check(claims: Claims, settings: IdentitySettings) -> Identity:
    """The identity behind verified claims, or `Rejected` with the reason."""
    sub, email = claims.get("sub"), claims.get("email") or ""
    if not sub or not email:
        raise Rejected("no_user")
    if email.endswith(SERVICE_ACCOUNT_DOMAIN):
        raise Rejected("service_account")  # the system identity uses event_agent_mcp (DEC-0007)
    surface = settings.surfaces_by_client.get(claims.get("client_id") or "")
    if surface is None:
        raise Rejected("undeclared_client")
    scopes = claims.get("scopes")
    if scopes is not None and ("openid" not in scopes or not any(s in scopes for s in EMAIL_SCOPES)):
        raise Rejected("missing_scope")
    if not claims.get("email_verified"):
        raise Rejected("unverified_email")
    domain = claims.get("hd") or email.rpartition("@")[2]
    if domain not in settings.allowed_domains:
        raise Rejected("wrong_domain")
    if sub in settings.blocked_user_ids or email in settings.blocked_emails:
        raise Rejected("blocked")
    return Identity(sub, email, domain, surface, claims["client_id"], int(claims["exp"]))
