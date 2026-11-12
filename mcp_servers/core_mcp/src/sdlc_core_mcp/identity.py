"""Resolve the caller of the current MCP request: validated token -> Principal -> policy.

The policy middleware resolves the Identity once per request (one config snapshot) and keeps
it in request-scoped state; tools read it with `request_identity()`.
"""

from dataclasses import dataclass

from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token, get_context
from sdlc_auth import Principal, principal_from_claims
from sdlc_config import EffectivePolicy, PolicyCache, Snapshot

_STATE_KEY = "sdlc_identity"


@dataclass(frozen=True)
class Identity:
    principal: Principal
    snapshot: Snapshot
    policy: EffectivePolicy
    request_id: str = ""  # correlates all audit records (and server logs) of one request
    user_alias: str | None = None  # users.yaml entry matched by the token oid (direct member)


def current_principal() -> Principal | None:
    """Principal for the current request, or None if the request carries no validated token."""
    access = get_access_token()
    return principal_from_claims(access.claims) if access else None


async def resolve_identity(
    principal: Principal,
    snapshot: Snapshot,
    cache: PolicyCache,
    request_id: str = "",
) -> Identity:
    """Membership from app roles and users.yaml only (CH-0011)."""
    user = snapshot.users.alias_for(principal.oid)  # oid only, never the email claim
    policy = cache.get(snapshot, principal.app_roles, user)
    return Identity(principal, snapshot, policy, request_id, user)


async def remember_identity(identity: Identity) -> None:
    await get_context().set_state(_STATE_KEY, identity, serializable=False)  # request-scoped


async def request_identity() -> Identity:
    """The Identity resolved by the policy middleware for this request."""
    identity = await get_context().get_state(_STATE_KEY)
    if identity is None:
        raise ToolError("authentication required")
    return identity
