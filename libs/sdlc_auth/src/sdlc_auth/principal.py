"""The authenticated user, normalized from validated Entra access-token claims."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Principal:
    oid: str  # Entra object ID: the stable user identifier used for audit and caching
    tid: str
    upn: str | None
    name: str | None
    group_ids: frozenset[str]  # from the token; empty when groups_overage is True
    groups_overage: bool  # token omitted groups (too many); resolve via Graph
    scopes: tuple[str, ...]


def principal_from_claims(claims: Mapping[str, Any]) -> Principal:
    """Build a Principal from claims that have ALREADY been validated (signature, iss, aud...)."""
    oid, tid = claims.get("oid"), claims.get("tid")
    if not oid or not tid:
        raise ValueError("token has no oid/tid claim; not an Entra user token")
    claim_names = claims.get("_claim_names") or {}
    overage = "groups" in claim_names or claims.get("hasgroups") is True
    groups = claims.get("groups") or []
    scp = claims.get("scp") or claims.get("scope") or ""
    return Principal(
        oid=str(oid),
        tid=str(tid),
        upn=claims.get("preferred_username") or claims.get("upn"),
        name=claims.get("name"),
        group_ids=frozenset() if overage else frozenset(str(g).lower() for g in groups),
        groups_overage=overage,
        scopes=tuple(scp.split() if isinstance(scp, str) else scp),
    )
