"""Who is calling, checked against the active configuration (Identity component; DEC-0010).

`identify(headers, settings, tokens, env=..., audiences=...)` follows `identity.mode`:

- `caller_token`: sdlc_ui or the agent runtime forwards the user in `X-SDLC-User-Id` and
  `X-SDLC-User-Email`, and proves who it is with its service account's Google ID token. Only declared
  callers can speak for a user; each names the surface.
- `trusted_header`: the same headers without caller proof, for the local environment only.
- `oauth` (DEC-0001, off for now): the user's own Google token, issued to a declared OAuth client.

Whatever the mode, the user must have a well-formed account ID and email in an allowed domain, not be a
service account and not be on the block list. Google tokens are verified by `GoogleTokens`: ID tokens
against Google's signing keys, access tokens by introspection, cached per instance for 300 seconds.

Every refusal is a `Rejected` with a reason for the audit record; tokens are never logged.
"""

from sdlc_identity.check import MODES, Identity, IdentitySettings, check
from sdlc_identity.forwarded import SURFACE_HEADER, USER_EMAIL_HEADER, USER_ID_HEADER, identify
from sdlc_identity.tokens import GoogleTokens, Rejected

__all__ = [
    "MODES",
    "SURFACE_HEADER",
    "USER_EMAIL_HEADER",
    "USER_ID_HEADER",
    "GoogleTokens",
    "Identity",
    "IdentitySettings",
    "Rejected",
    "check",
    "identify",
]
