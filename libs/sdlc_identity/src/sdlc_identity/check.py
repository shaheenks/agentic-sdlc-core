"""The checks that depend on the active configuration, run on every request."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sdlc_identity.tokens import Claims, Rejected

# How a service learns who the user is (`identity.mode`, DEC-0010).
CALLER_TOKEN = "caller_token"  # a declared service account forwards the user, proven by its Google ID token
TRUSTED_HEADER = "trusted_header"  # the user headers are trusted as sent; local environment only
OAUTH = "oauth"  # the user's own Google token (DEC-0001); off for now
MODES = (CALLER_TOKEN, TRUSTED_HEADER, OAUTH)
LOCAL_ONLY_MODES = (TRUSTED_HEADER,)

EMAIL_SCOPES = ("email", "https://www.googleapis.com/auth/userinfo.email")
SERVICE_ACCOUNT_DOMAIN = ".gserviceaccount.com"
USER_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")  # also a folder name under the user's prefix
EMAIL = re.compile(r"^[^@\s/]+@[a-z0-9.-]+\.[a-z]+$")


@dataclass(frozen=True)
class Identity:
    """A user. `user_id` is the Google account ID (`sub`), the owner of everything the user has. `caller` is
    what vouched for the user: the forwarding service account, the OAuth client, or `trusted_header`."""

    user_id: str
    email: str
    domain: str
    surface: str
    caller: str


@dataclass(frozen=True)
class IdentitySettings:
    mode: str
    allowed_domains: frozenset[str]
    surfaces_by_caller: Mapping[str, str]  # service account email or unique ID -> surface
    surfaces_by_client: Mapping[str, str]  # OAuth client ID -> surface (mode oauth)
    blocked_user_ids: frozenset[str]
    blocked_emails: frozenset[str]
    # Surfaces marked `system: true`: their callers are the system identity of unattended runs, never a user's
    # forwarder (DEC-0015).
    system_surfaces: frozenset[str] = frozenset()

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "IdentitySettings":
        """From a compiled bundle: `identity.mode`, `identity.allowed_domains`, `identity.callers` and
        `identity.clients` ({surface: [IDs]}), and `blocked` ([{user_id | email, reason}])."""
        identity = config.get("identity") or {}

        def by_id(key: str, lower: bool) -> dict[str, str]:
            return {
                (i.lower() if lower else i): surface for surface, ids in (identity.get(key) or {}).items() for i in ids
            }

        blocked = config.get("blocked") or []
        return cls(
            mode=str(identity.get("mode") or ""),
            allowed_domains=frozenset(d.lower() for d in identity.get("allowed_domains") or ()),
            surfaces_by_caller=by_id("callers", lower=True),
            surfaces_by_client=by_id("clients", lower=False),
            blocked_user_ids=frozenset(str(b["user_id"]) for b in blocked if b.get("user_id")),
            blocked_emails=frozenset(str(b["email"]).lower() for b in blocked if b.get("email")),
            system_surfaces=frozenset(s for s, e in (config.get("surfaces") or {}).items() if (e or {}).get("system")),
        )


def check_user(user_id: str, email: str, settings: IdentitySettings, surface: str, caller: str) -> Identity:
    """The checks every user passes, however they were identified: a well-formed account, not a service
    account, an allowed domain, not blocked."""
    if not user_id or not email:
        raise Rejected("no_user")
    if not USER_ID.match(user_id) or not EMAIL.match(email):
        raise Rejected("invalid_user")
    if email.endswith(SERVICE_ACCOUNT_DOMAIN):
        raise Rejected("service_account")  # the system identity uses event_agent_mcp (DEC-0007)
    domain = email.rpartition("@")[2]
    if domain not in settings.allowed_domains:
        raise Rejected("wrong_domain")
    if user_id in settings.blocked_user_ids or email in settings.blocked_emails:
        raise Rejected("blocked")
    return Identity(user_id, email, domain, surface, caller)


def check(claims: Claims, settings: IdentitySettings) -> Identity:
    """Mode `oauth`: the user behind their own verified token, or `Rejected` with the reason."""
    sub, email = claims.get("sub") or "", claims.get("email") or ""
    if not sub or not email:
        raise Rejected("no_user")
    if email.endswith(SERVICE_ACCOUNT_DOMAIN):
        raise Rejected("service_account")
    client_id = claims.get("client_id") or ""
    surface = settings.surfaces_by_client.get(client_id)
    if surface is None:
        raise Rejected("undeclared_client")
    scopes = claims.get("scopes")
    if scopes is not None and ("openid" not in scopes or not any(s in scopes for s in EMAIL_SCOPES)):
        raise Rejected("missing_scope")
    if not claims.get("email_verified"):
        raise Rejected("unverified_email")
    if claims.get("hd") and claims["hd"] not in settings.allowed_domains:
        raise Rejected("wrong_domain")
    return check_user(sub, email, settings, surface, client_id)
