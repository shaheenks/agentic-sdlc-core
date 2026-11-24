"""Who is calling: Google account tokens, verified and checked against the active configuration.

Two steps (Identity component; DEC-0001, DEC-0009):

1. `GoogleTokens.claims(token)` proves the token is Google's and still valid: an ID token (a JWT) is checked
   locally against Google's signing keys, an access token by Google's token introspection. Verified claims
   are cached per instance for 300 seconds, or until the token expires if sooner.
2. `check(claims, settings)` applies the active configuration on every request: the token must be issued to a
   declared OAuth client (which names the surface), carry the `openid` and `email` scopes, belong to an
   allowed Cloud Identity domain, not be a service account, and not be on the block list.

Every refusal is a `Rejected` with a reason for the audit record; the token itself is never logged.
"""

from sdlc_identity.check import Identity, IdentitySettings, check
from sdlc_identity.tokens import GoogleTokens, Rejected

__all__ = ["GoogleTokens", "Identity", "IdentitySettings", "Rejected", "check"]
