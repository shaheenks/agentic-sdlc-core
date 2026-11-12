"""The authenticated user, normalized from validated Entra access-token claims.

Membership comes only from Entra app roles (the `roles` claim) and users.yaml (matched on `oid`).
A `groups` claim, if a tenant still sends one, is ignored (CH-0011).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Principal:
    oid: str  # Entra object ID: the stable user identifier used for audit and caching
    tid: str
    upn: str | None
    name: str | None
    scopes: tuple[str, ...]
    app_roles: frozenset[str] = frozenset()  # Entra app roles (`roles` claim)


def principal_from_claims(claims: Mapping[str, Any]) -> Principal:
    """Build a Principal from claims that have ALREADY been validated (signature, iss, aud...)."""
    oid, tid = claims.get("oid"), claims.get("tid")
    if not oid or not tid:
        raise ValueError("token has no oid/tid claim; not an Entra user token")
    roles = claims.get("roles") or []
    scp = claims.get("scp") or claims.get("scope") or ""
    return Principal(
        oid=str(oid),
        tid=str(tid),
        upn=claims.get("preferred_username") or claims.get("upn"),
        name=claims.get("name"),
        scopes=tuple(scp.split() if isinstance(scp, str) else scp),
        app_roles=frozenset(str(r) for r in roles) if isinstance(roles, list) else frozenset(),
    )
