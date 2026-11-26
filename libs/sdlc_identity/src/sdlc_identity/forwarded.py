"""Who the user is, for each `identity.mode` (DEC-0010).

In modes `caller_token` and `trusted_header` the user arrives in two headers set by sdlc_ui (from the IAP
assertion it verified) or by the agent runtime (from the session sdlc_ui started):

- `X-SDLC-User-Id`: the Google account ID (`sub`; IAP's `accounts.google.com:` prefix is accepted);
- `X-SDLC-User-Email`: the account's email.

`caller_token`: the request also carries `Authorization: Bearer <Google ID token>` of the calling service
account, with this service's URL as audience. The account must be declared under `identity.callers`, which
names the surface. Anything else is refused, so only declared callers can speak for a user.

`trusted_header`: no caller proof; the surface comes from `X-SDLC-Surface` and must be a declared caller.
Allowed only in the `local` environment.

A caller declared for a system surface (`system: true`) is the system identity of unattended runs: it never speaks
for a user, and `identify_system` is the only way it is accepted (DEC-0015).
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from sdlc_identity.check import (
    CALLER_TOKEN,
    LOCAL_ONLY_MODES,
    OAUTH,
    TRUSTED_HEADER,
    Identity,
    IdentitySettings,
    check,
    check_user,
)
from sdlc_identity.tokens import Claims, GoogleTokens, Rejected

USER_ID_HEADER = "x-sdlc-user-id"
USER_EMAIL_HEADER = "x-sdlc-user-email"
SURFACE_HEADER = "x-sdlc-surface"
IAP_PREFIX = "accounts.google.com:"
LOCAL_ENV = "local"


def bearer(headers: Mapping[str, str]) -> str:
    value = headers.get("authorization") or ""
    return value[7:].strip() if value[:7].lower() == "bearer " else ""


def check_caller(claims: Claims, settings: IdentitySettings, audiences: Collection[str]) -> tuple[str, str]:
    """The surface and account of a calling service account, from its verified Google ID token."""
    if claims.get("kind") != "id":
        raise Rejected("not_an_id_token")
    if claims.get("client_id") not in audiences:  # an ID token's `aud`
        raise Rejected("wrong_audience")
    account = (claims.get("email") if claims.get("email_verified") else "") or claims.get("sub") or ""
    surface = settings.surfaces_by_caller.get(account.lower())
    if surface is None:
        raise Rejected("undeclared_caller")
    return surface, account


def forwarded_user(headers: Mapping[str, str], settings: IdentitySettings, surface: str, caller: str) -> Identity:
    if surface in settings.system_surfaces:
        raise Rejected("system_caller")  # the system identity never speaks for a user
    user_id = (headers.get(USER_ID_HEADER) or "").strip().removeprefix(IAP_PREFIX)
    email = (headers.get(USER_EMAIL_HEADER) or "").strip().lower().removeprefix(IAP_PREFIX)
    return check_user(user_id, email, settings, surface, caller)


async def identify(
    headers: Mapping[str, str],
    settings: IdentitySettings,
    tokens: GoogleTokens,
    *,
    env: str,
    audiences: Collection[str],
) -> Identity:
    """The user of one request, or `Rejected`. `headers` must look names up case-insensitively."""
    if settings.mode in LOCAL_ONLY_MODES and env != LOCAL_ENV:
        raise Rejected("mode_not_allowed")
    if settings.mode == CALLER_TOKEN:
        token = bearer(headers)
        if not token:
            raise Rejected("no_token")
        surface, account = check_caller(await tokens.claims(token), settings, audiences)
        return forwarded_user(headers, settings, surface, account)
    if settings.mode == TRUSTED_HEADER:
        surface = (headers.get(SURFACE_HEADER) or "").strip()
        if surface not in set(settings.surfaces_by_caller.values()):
            raise Rejected("undeclared_caller")
        return forwarded_user(headers, settings, surface, TRUSTED_HEADER)
    if settings.mode == OAUTH:
        token = bearer(headers)
        if not token:
            raise Rejected("no_token")
        return check(await tokens.claims(token), settings)
    raise Rejected("identity_not_configured")


@dataclass(frozen=True)
class SystemCaller:
    """The system identity of an unattended run: the declared service account of a system surface."""

    account: str
    surface: str


async def identify_system(
    headers: Mapping[str, str],
    settings: IdentitySettings,
    tokens: GoogleTokens,
    *,
    env: str,
    audiences: Collection[str],
) -> SystemCaller:
    """The system identity of one request to event_agent_mcp, or `Rejected` (FR-IDN-004, DEC-0015). Its caller must
    prove itself with its service account's Google ID token whatever the identity mode; only in the local environment,
    in mode trusted_header, may it name its surface instead. A request that forwards a user is refused."""
    if headers.get(USER_ID_HEADER) or headers.get(USER_EMAIL_HEADER):
        raise Rejected("user_on_system_surface")
    if settings.mode == TRUSTED_HEADER and env == LOCAL_ENV and not bearer(headers):
        surface = (headers.get(SURFACE_HEADER) or "").strip()
        if surface not in settings.system_surfaces or surface not in set(settings.surfaces_by_caller.values()):
            raise Rejected("undeclared_caller")
        return SystemCaller(TRUSTED_HEADER, surface)
    token = bearer(headers)
    if not token:
        raise Rejected("no_token")
    surface, account = check_caller(await tokens.claims(token), settings, audiences)
    if surface not in settings.system_surfaces:
        raise Rejected("not_a_system_caller")
    return SystemCaller(account, surface)
