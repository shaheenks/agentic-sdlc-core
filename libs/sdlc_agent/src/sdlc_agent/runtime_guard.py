"""The checks every entry point runs before the agent does (CH-0014).

`sdlc_web` (adk web, local and dev) and the Agent Runtime app (`agents/user_agent/runtime_app.py`,
GCP-native) both use these, so a user is bound the same way wherever the agent is hosted:
- the caller's Entra token is validated (signature, issuer, audience, scope, tenant); anything else
  fails closed;
- the ADK user id is the token's `oid`, never a value the client sends;
- client-supplied session state never carries tokens or server-owned keys.
Authorization stays in the MCP server; these checks only authenticate and bind identity.
"""

from collections.abc import Mapping
from typing import Any

from sdlc_auth import principal_from_claims
from sdlc_auth.adk import USER_TOKEN_STATE_KEY

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


async def verify_user(verifier: Any, token: str | None) -> str:
    """The `oid` of a valid Entra user token, or NotAuthenticated (fail closed). `verifier` is a
    fastmcp TokenVerifier (sdlc_auth.entra.EntraTokenVerifier)."""
    if not token or not isinstance(token, str):
        raise NotAuthenticated("sign-in required")
    access = await verifier.load_access_token(token)
    if access is None:
        raise NotAuthenticated("invalid or expired token")
    try:
        return principal_from_claims(access.claims).oid
    except ValueError:
        raise NotAuthenticated("not a user token") from None
