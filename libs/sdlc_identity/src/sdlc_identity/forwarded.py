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
"""

from collections.abc import Collection, Mapping

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
