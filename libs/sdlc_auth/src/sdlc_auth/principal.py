"""The authenticated user, normalized from validated Entra access-token claims."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

_GUID = re.compile(r"^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")


@dataclass(frozen=True)
class Principal:
    oid: str  # Entra object ID: the stable user identifier used for audit and caching
    tid: str
    upn: str | None
    name: str | None
    group_ids: frozenset[str]  # from the token; empty when groups_overage is True
    groups_overage: bool  # token omitted groups (too many); resolve via Graph
    scopes: tuple[str, ...]
    app_roles: frozenset[str] = frozenset()  # Entra app roles (`roles` claim), enterprise path
    # Group claim values that are not object IDs (e.g. on-prem sAMAccountName): never mapped
    non_guid_group_claims: int = 0


def principal_from_claims(claims: Mapping[str, Any]) -> Principal:
    """Build a Principal from claims that have ALREADY been validated (signature, iss, aud...)."""
    oid, tid = claims.get("oid"), claims.get("tid")
    if not oid or not tid:
        raise ValueError("token has no oid/tid claim; not an Entra user token")
    claim_names = claims.get("_claim_names") or {}
    overage = "groups" in claim_names or claims.get("hasgroups") is True
    groups = claims.get("groups") or []
    guid_groups = [str(g).lower() for g in groups if _GUID.match(str(g))]
    roles = claims.get("roles") or []
    scp = claims.get("scp") or claims.get("scope") or ""
    return Principal(
        oid=str(oid),
        tid=str(tid),
        upn=claims.get("preferred_username") or claims.get("upn"),
        name=claims.get("name"),
        group_ids=frozenset() if overage else frozenset(guid_groups),
        groups_overage=overage,
        scopes=tuple(scp.split() if isinstance(scp, str) else scp),
        app_roles=frozenset(str(r) for r in roles) if isinstance(roles, list) else frozenset(),
        non_guid_group_claims=0 if overage else len(groups) - len(guid_groups),
    )
