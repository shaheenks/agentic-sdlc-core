"""Entra ID identity.

Server-side token verification lives in sdlc_auth.entra (needs the `server` extra).
"""

from sdlc_auth.principal import Principal, principal_from_claims

__all__ = [
    "Principal",
    "principal_from_claims",
]
