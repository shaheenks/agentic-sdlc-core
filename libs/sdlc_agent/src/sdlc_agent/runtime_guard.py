"""The checks every entry point runs before the agent does (CH-0014).

`sdlc_web` (adk web, local and dev) and the Agent Runtime app (`agents/user_agent/runtime_app.py`,
GCP-native) both use these, so a user is bound the same way wherever the agent is hosted:
- the caller's token is validated by the stack's verifier (`verifier_from_env`): the Entra stack's
  (signature, issuer, audience, scope, tenant) or, with `SDLC_IDENTITY_PROVIDER=google`, the GCP
  stack's (Google ID token for our OAuth clients, verified email, allowed domain; CH-0022);
  anything else fails closed;
- the ADK user id is the token's user id (Entra `oid`, Google `sub`), never a value the client
  sends;
- client-supplied session state never carries tokens or server-owned keys.
Authorization stays in the MCP server; these checks only authenticate and bind identity.
"""

import os
from collections.abc import Mapping
from typing import Any

from sdlc_auth import Principal, principal_from_claims
from sdlc_auth.adk import USER_TOKEN_STATE_KEY

ENTRA, GOOGLE = "entra", "google"
GOOGLE_ISSUER = "https://accounts.google.com"  # = sdlc_auth.google.GOOGLE_ISSUER

# State keys a client may never set: per-invocation (temp:, where a token could live), shared
# scopes (app:, user:), server-owned keys (sdlc_, e.g. the active team, version-03 G9), plus the
# user-token key itself.
UNTRUSTED_STATE_PREFIXES = ("temp:", "app:", "user:", "sdlc_")


class NotAuthenticated(PermissionError):
    """No valid user token: the caller gets no answer and no session."""


def clean_state(state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Client state without tokens or keys only the server may set."""
    return {
        k: v
        for k, v in (state or {}).items()
        if k != USER_TOKEN_STATE_KEY and not k.startswith(UNTRUSTED_STATE_PREFIXES)
    }


def identity_provider(environ: Mapping[str, str] = os.environ) -> str:
    """The stack this agent serves: SDLC_IDENTITY_PROVIDER, `entra` (default) or `google`."""
    provider = environ.get("SDLC_IDENTITY_PROVIDER", ENTRA).strip().lower() or ENTRA
    if provider not in (ENTRA, GOOGLE):
        raise SystemExit(f"SDLC_IDENTITY_PROVIDER must be {ENTRA} or {GOOGLE} (fail closed)")
    return provider


def verifier_from_env(environ: Mapping[str, str] = os.environ) -> Any:
    """The user token verifier of this agent's stack. Missing settings stop startup."""
    if identity_provider(environ) == GOOGLE:
        from sdlc_auth.google import google_verifier_from_env

        return google_verifier_from_env()
    from sdlc_auth.entra import verifier_from_env as entra_verifier_from_env

    return entra_verifier_from_env()


def principal_of(claims: Mapping[str, Any]) -> Principal:
    """The Principal of claims a verifier has ALREADY validated. Each verifier accepts one issuer,
    so the issuer tells which stack's claims these are."""
    if claims.get("iss") == GOOGLE_ISSUER:
        from sdlc_auth.google import principal_from_google_claims

        return principal_from_google_claims(claims)
    return principal_from_claims(claims)


async def verify_user(verifier: Any, token: str | None) -> str:
    """The user id (Entra `oid` or Google `sub`) of a valid user token, or NotAuthenticated (fail
    closed). `verifier` is a fastmcp TokenVerifier (`verifier_from_env`)."""
    if not token or not isinstance(token, str):
        raise NotAuthenticated("sign-in required")
    access = await verifier.load_access_token(token)
    if access is None:
        raise NotAuthenticated("invalid or expired token")
    try:
        return principal_of(access.claims).oid
    except ValueError:
        raise NotAuthenticated("not a user token") from None
