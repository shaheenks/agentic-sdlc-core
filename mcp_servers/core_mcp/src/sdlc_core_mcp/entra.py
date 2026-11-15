"""The Entra identity adapter of core_mcp (CH-0020).

How the Entra stack reads a verified token: the user is the `oid`, membership comes from Entra
app roles (the `roles` claim) and users.yaml matched on `oid` (CH-0011). Everything else of the
server lives in `sdlc_mcp`, shared with other server components.
"""

import time
from collections.abc import Mapping
from typing import Any

from sdlc_auth import Principal, principal_from_claims
from sdlc_config import Snapshot
from sdlc_config.model import UserMap


class EntraAdapter:
    name = "entra"

    def principal(self, claims: Mapping[str, Any]) -> Principal:
        return principal_from_claims(claims)

    def memberships(self, principal: Principal, snapshot: Snapshot) -> frozenset[str]:
        return frozenset(f"app_role:{r}" for r in principal.app_roles)

    def user_alias(self, principal: Principal, users: UserMap) -> str | None:
        return users.alias_for(principal.oid)  # oid only, never the email claim

    def describe(self, principal: Principal) -> dict[str, Any]:
        return {
            "oid": principal.oid,
            "upn": principal.upn,
            "name": principal.name,
            "tenant_id": principal.tid,
            "app_roles": sorted(principal.app_roles),
        }

    def rejection(self, claims: dict[str, Any], snapshot: Snapshot) -> tuple[str, dict[str, Any]]:
        claimed = {
            k: claims.get(k)
            for k in ("oid", "preferred_username", "tid", "aud", "exp", "iss")
            if claims.get(k) is not None
        }
        platform = snapshot.platform
        exp = claims.get("exp")
        if str(claims.get("oid", "")).lower() in snapshot.blocked:
            reason = "blocked"  # E3 block list (claimed oid; the token was rejected either way)
        elif isinstance(exp, int | float) and exp < time.time():
            reason = "expired"
        elif claims.get("tid") != platform.tenant_id:
            reason = "wrong_tenant"
        elif claims.get("iss") != platform.issuer:
            reason = "wrong_issuer"
        elif claims.get("aud") not in platform.audience:
            reason = "wrong_audience"
        elif not set(str(claims.get("scp", "")).split()) >= set(platform.required_scopes):
            reason = "missing_scope"
        else:
            reason = "invalid_token"  # e.g. bad signature, app-only token, unknown signing key
        return reason, claimed


ENTRA = EntraAdapter()
