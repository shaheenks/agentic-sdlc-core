"""Resolve the caller of the current MCP request: validated token -> Principal -> policy.

The policy middleware resolves the Identity once per request (one config snapshot) and keeps
it in request-scoped state; tools read it with `request_identity()`.
"""

from dataclasses import dataclass

from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token, get_context
from sdlc_auth import GroupResolver, Principal, effective_group_ids, principal_from_claims
from sdlc_auth.groups import GroupSource
from sdlc_config import EffectivePolicy, PolicyCache, Snapshot

_STATE_KEY = "sdlc_identity"


@dataclass(frozen=True)
class Identity:
    principal: Principal
    group_aliases: tuple[str, ...]
    unmapped_group_count: int
    group_source: GroupSource
    snapshot: Snapshot
    policy: EffectivePolicy


def current_principal() -> Principal | None:
    """Principal for the current request, or None if the request carries no validated token."""
    access = get_access_token()
    return principal_from_claims(access.claims) if access else None


async def resolve_identity(
    principal: Principal,
    snapshot: Snapshot,
    group_resolver: GroupResolver | None,
    cache: PolicyCache,
) -> Identity:
    group_ids, source = await effective_group_ids(principal, group_resolver)
    aliases, unmapped = snapshot.groups.aliases_for(group_ids)
    policy = cache.get(snapshot, aliases, principal.app_roles)
    return Identity(principal, aliases, unmapped, source, snapshot, policy)


async def remember_identity(identity: Identity) -> None:
    await get_context().set_state(_STATE_KEY, identity, serializable=False)  # request-scoped


async def request_identity() -> Identity:
    """The Identity resolved by the policy middleware for this request."""
    identity = await get_context().get_state(_STATE_KEY)
    if identity is None:
        raise ToolError("authentication required")
    return identity
