"""Resolve the caller of the current MCP request: validated token → Principal → group aliases."""

from dataclasses import dataclass

from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token
from sdlc_auth import GroupResolver, Principal, effective_group_ids, principal_from_claims
from sdlc_auth.groups import GroupSource
from sdlc_config import Snapshot


@dataclass(frozen=True)
class Identity:
    principal: Principal
    group_aliases: tuple[str, ...]
    unmapped_group_count: int
    group_source: GroupSource
    config_version: str


def current_principal() -> Principal | None:
    """Principal for the current request, or None if the request carries no validated token."""
    access = get_access_token()
    return principal_from_claims(access.claims) if access else None


async def current_identity(snapshot: Snapshot, resolver: GroupResolver | None) -> Identity:
    principal = current_principal()
    if principal is None:
        raise ToolError("authentication required")
    group_ids, source = await effective_group_ids(principal, resolver)
    aliases, unmapped = snapshot.groups.aliases_for(group_ids)
    return Identity(principal, aliases, unmapped, source, snapshot.version)
