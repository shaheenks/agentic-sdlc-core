"""Google Groups membership for the GCP stack (CH-0021, design N10).

The GCP stack's tokens carry no groups: the MCP server asks the Cloud Identity Groups API with its
OWN credentials (a service account with the Groups Reader admin role) which of the groups bound
in config the verified user belongs to. Only the configured groups are ever answered: the user's
other groups are not looked up (direct) or are dropped (transitive).

  - direct (Cloud Identity Free): for each configured group, `groups:lookup` (its resource name,
    cached) then `memberships:lookup` for the user. Direct membership only: no nested groups.
  - transitive (Premium): one `memberships:searchTransitiveGroups` for the user, paged.

Answers are cached per user for `cache_seconds`; removing someone from a group takes effect
within that time (FR-IDN-004). A lookup error is failed closed and not cached:
  - direct: a group whose lookup fails gives no roles to this request; the user's other groups still
    count (CH-0026: groups only add access, so one unresolvable group must not remove them all).
    Cloud Identity answers `groups:lookup` with 403, not 404, for an address it cannot find.
  - transitive: the one call has no per-group answer, so an error gives NO groups.
The log names the group and the error, never the user's email. `check` resolves each configured
group for `sdlc-config check-groups`.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Protocol

import httpx

log = logging.getLogger("sdlc.auth.groups")

API = "https://cloudidentity.googleapis.com/v1"
SCOPE = "https://www.googleapis.com/auth/cloud-identity.groups.readonly"
DIRECT, TRANSITIVE = "direct", "transitive"
_LABEL = "cloudidentity.googleapis.com/groups.discussion_forum"


class GroupDirectory(Protocol):
    async def groups_of(self, email: str, candidates: Iterable[str]) -> frozenset[str]:
        """The candidate group emails (lower-case) that `email` is a member of."""
        ...


class StaticGroups:
    """A fixed email -> groups map: tests and local runs without the Groups API."""

    def __init__(self, members: Mapping[str, Iterable[str]]):
        self.members = {e.lower(): frozenset(g.lower() for g in gs) for e, gs in members.items()}

    async def groups_of(self, email: str, candidates: Iterable[str]) -> frozenset[str]:
        wanted = frozenset(c.lower() for c in candidates)
        return self.members.get(email.lower(), frozenset()) & wanted


class LookupFailed(Exception):
    """A Groups API call failed: the caller gets no groups."""


TokenProvider = Callable[[], Awaitable[str]]  # an OAuth access token for SCOPE


def adc_token_provider() -> TokenProvider:
    """Application Default Credentials (the server's service account), refreshed when stale."""
    import google.auth  # only where the Groups API is used
    from google.auth.transport.requests import Request

    credentials, _ = google.auth.default(scopes=[SCOPE])

    async def token() -> str:
        if not credentials.valid:
            await asyncio.to_thread(credentials.refresh, Request())
        return credentials.token

    return token


class CloudIdentityGroups:
    def __init__(
        self,
        *,
        mode: str = DIRECT,
        cache_seconds: int = 300,
        token: TokenProvider | None = None,
        client: httpx.AsyncClient | None = None,
        clock: Callable[[], float] = time.monotonic,
        quota_project: str | None = None,
    ):
        if mode not in (DIRECT, TRANSITIVE):
            raise ValueError(f"unknown group lookup mode {mode!r}")
        self.mode = mode
        self.cache_seconds = cache_seconds
        self._token = token or adc_token_provider()
        self._client = client or httpx.AsyncClient(timeout=10.0)
        self._clock = clock
        # Billing project for user ADC (local runs, CH-0022); a service account needs none.
        self._quota_project = quota_project
        self._users: dict[tuple[str, frozenset[str]], tuple[float, frozenset[str]]] = {}
        self._group_names: dict[str, str] = {}  # group email -> groups/<id>

    async def groups_of(self, email: str, candidates: Iterable[str]) -> frozenset[str]:
        email = email.lower()
        wanted = frozenset(c.lower() for c in candidates)
        if not email or not wanted:
            return frozenset()
        key = (email, wanted)
        hit = self._users.get(key)
        if hit is not None and hit[0] > self._clock():
            return hit[1]
        if self.mode == DIRECT:
            groups, complete = await self._direct(email, wanted)
        else:
            try:
                groups, complete = await self._transitive(email, wanted), True
            except (LookupFailed, httpx.HTTPError) as e:
                log.warning("group lookup failed (%s): no group roles for this request", _what(e))
                return frozenset()
        if complete and self.cache_seconds > 0:
            self._users[key] = (self._clock() + self.cache_seconds, groups)
        return groups

    async def _get(self, path: str, params: dict[str, str]) -> httpx.Response:
        headers = {"Authorization": f"Bearer {await self._token()}"}
        if self._quota_project:
            headers["x-goog-user-project"] = self._quota_project
        return await self._client.get(f"{API}/{path}", params=params, headers=headers)

    async def _group_name(self, group: str) -> str | None:
        if group in self._group_names:
            return self._group_names[group]
        r = await self._get("groups:lookup", {"groupKey.id": group})
        if r.status_code == 404:  # no such group (yet): no members; asked again next time
            log.warning("group %s not found in Cloud Identity", group)
            return None
        # 403: no group with this address (Cloud Identity does not say 404 for those), or the
        # caller lacks the Groups Reader role; sdlc-config check-groups tells which groups
        if r.status_code != 200:
            raise LookupFailed(f"groups:lookup HTTP {r.status_code}")
        name = r.json().get("name")
        if not name:
            raise LookupFailed("groups:lookup returned no name")
        self._group_names[group] = name  # a group's resource name never changes
        return name

    async def _is_member(self, group: str, email: str) -> bool:
        name = await self._group_name(group)
        if not name:
            return False
        r = await self._get(f"{name}/memberships:lookup", {"memberKey.id": email})
        if r.status_code == 404:
            return False
        if r.status_code != 200:
            raise LookupFailed(f"memberships:lookup HTTP {r.status_code}")
        return True

    async def check(self, groups: Iterable[str]) -> dict[str, str]:
        """Each group (lower-case) -> "ok", "NOT FOUND" or "NOT RESOLVED (<why>)". Read-only."""
        outcome: dict[str, str] = {}
        for group in sorted({g.lower() for g in groups}):
            try:
                outcome[group] = "ok" if await self._group_name(group) else "NOT FOUND"
            except (LookupFailed, httpx.HTTPError) as e:
                outcome[group] = f"NOT RESOLVED ({_what(e)})"
        return outcome

    async def _member_or_none(self, group: str, email: str) -> bool | None:
        """Membership in one group; None when its lookup failed (no roles from it, CH-0026)."""
        try:
            return await self._is_member(group, email)
        except (LookupFailed, httpx.HTTPError) as e:
            log.warning(
                "group lookup failed for %s (%s): no roles from this group for this request",
                group,
                _what(e),
            )
            return None

    async def _direct(self, email: str, wanted: frozenset[str]) -> tuple[frozenset[str], bool]:
        """The groups found, and whether every lookup answered (only then is it cached)."""
        ordered = sorted(wanted)
        found = await asyncio.gather(*(self._member_or_none(g, email) for g in ordered))
        groups = frozenset(g for g, member in zip(ordered, found, strict=True) if member)
        return groups, None not in found

    async def _transitive(self, email: str, wanted: frozenset[str]) -> frozenset[str]:
        query = f"member_key_id == '{_quote(email)}' && '{_LABEL}' in labels"
        groups: set[str] = set()
        page = ""
        while True:
            params = {"query": query, **({"pageToken": page} if page else {})}
            r = await self._get("groups/-/memberships:searchTransitiveGroups", params)
            if r.status_code != 200:
                raise LookupFailed(f"searchTransitiveGroups HTTP {r.status_code}")
            body = r.json()
            for m in body.get("memberships", []):
                group = str(m.get("groupKey", {}).get("id", "")).lower()
                if group:
                    groups.add(group)
            page = body.get("nextPageToken", "")
            if not page:
                return frozenset(groups) & wanted


def _quote(email: str) -> str:
    if "'" in email or "\\" in email:
        raise LookupFailed("unexpected character in email")
    return email


def _what(e: Exception) -> str:
    return str(e) if isinstance(e, LookupFailed) else type(e).__name__
