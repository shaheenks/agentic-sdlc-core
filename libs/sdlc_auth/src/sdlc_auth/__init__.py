"""Entra ID identity.

Server-side token verification lives in sdlc_auth.entra (needs the `server` extra).
"""

from sdlc_auth.groups import GraphGroupResolver, GroupResolver, effective_group_ids
from sdlc_auth.principal import Principal, principal_from_claims

__all__ = [
    "GraphGroupResolver",
    "GroupResolver",
    "Principal",
    "effective_group_ids",
    "principal_from_claims",
]
