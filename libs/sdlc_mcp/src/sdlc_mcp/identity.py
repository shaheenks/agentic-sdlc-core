"""Resolve the caller of the current MCP request: validated token -> Principal -> policy.

Who the caller is depends on the identity provider, so it comes from an `IdentityAdapter`
supplied by the server component (CH-0020): `core_mcp` passes the Entra adapter, `core_mcp_gcp`
the Google one. Nothing here knows which provider issued the token.

The policy middleware resolves the Identity once per request (one config snapshot) and keeps
it in request-scoped state; tools read it with `request_identity()`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token, get_context
from sdlc_auth import Principal
from sdlc_config import EffectivePolicy, PolicyCache, Snapshot

_STATE_KEY = "sdlc_identity"


class IdentityAdapter(Protocol):
    """What a server component supplies about its identity provider. The token itself is
    verified by the component's auth provider before any of this runs."""

    name: str  # e.g. "entra"

    def principal(self, claims: Mapping[str, Any]) -> Principal:
        """The caller from ALREADY validated claims; ValueError if it is not a user token."""
        ...

    def memberships(self, principal: Principal) -> frozenset[str]:
        """What the policy resolver matches role bindings against."""
        ...

    def user_key(self, principal: Principal) -> str:
        """The value users.yaml entries are matched on."""
        ...

    def describe(self, principal: Principal) -> dict[str, Any]:
        """The caller as `whoami` shows it."""
        ...

    def rejection(self, claims: dict[str, Any], snapshot: Snapshot) -> tuple[str, dict[str, Any]]:
        """Why a token the verifier REJECTED was refused, from its unverified claims, and the
        claims worth reporting (audit `auth_failure`)."""
        ...


@dataclass(frozen=True)
class Identity:
    principal: Principal
    snapshot: Snapshot
    policy: EffectivePolicy
    request_id: str = ""  # correlates all audit records (and server logs) of one request
    user_alias: str | None = None  # users.yaml entry matched by the adapter's user key


def current_principal(adapter: IdentityAdapter) -> Principal | None:
    """Principal for the current request, or None if the request carries no validated token."""
    access = get_access_token()
    return adapter.principal(access.claims) if access else None


async def resolve_identity(
    principal: Principal,
    snapshot: Snapshot,
    cache: PolicyCache,
    adapter: IdentityAdapter,
    request_id: str = "",
) -> Identity:
    """Membership from the adapter's memberships and users.yaml (never from a tool argument)."""
    user = snapshot.users.alias_for(adapter.user_key(principal))
    policy = cache.get(snapshot, adapter.memberships(principal), user)
    return Identity(principal, snapshot, policy, request_id, user)


async def remember_identity(identity: Identity) -> None:
    await get_context().set_state(_STATE_KEY, identity, serializable=False)  # request-scoped


async def request_identity() -> Identity:
    """The Identity resolved by the policy middleware for this request."""
    identity = await get_context().get_state(_STATE_KEY)
    if identity is None:
        raise ToolError("authentication required")
    return identity
