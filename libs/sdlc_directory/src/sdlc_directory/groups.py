"""Google group membership: a static list, or the Cloud Identity Groups API."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Protocol

import httpx

log = logging.getLogger("sdlc.directory")

API = "https://cloudidentity.googleapis.com/v1"
SCOPE = "https://www.googleapis.com/auth/cloud-identity.groups.readonly"
DIRECT, TRANSITIVE = "direct", "transitive"
_LABEL = "cloudidentity.googleapis.com/groups.discussion_forum"


class GroupLookup(Protocol):
    async def groups_of(self, email: str, candidates: Iterable[str]) -> frozenset[str]:
        """The candidate group emails (lower case) that `email` is a member of."""
        ...


class StaticGroups:
    """A fixed email-to-groups list: local runs and tests."""

    def __init__(self, members: Mapping[str, Iterable[str]]) -> None:
        self.members = {e.lower(): frozenset(g.lower() for g in gs) for e, gs in members.items()}

    async def groups_of(self, email: str, candidates: Iterable[str]) -> frozenset[str]:
        return self.members.get(email.lower(), frozenset()) & frozenset(c.lower() for c in candidates)


class LookupFailed(Exception):
    pass


TokenProvider = Callable[[], Awaitable[str]]


def adc_token_provider() -> TokenProvider:
    """The service's own credentials (Application Default Credentials), refreshed when stale."""
    import google.auth
    from google.auth.transport.requests import Request

    credentials, _ = google.auth.default(scopes=[SCOPE])

    async def token() -> str:
        if not credentials.valid:
            await asyncio.to_thread(credentials.refresh, Request())
        return credentials.token

    return token


class CloudIdentityGroups:
    """The Cloud Identity Groups API, called with the service's credentials, which need the Groups Reader
    admin role. `quota_project` is needed only with user credentials (local runs)."""

    def __init__(
        self,
        *,
        mode: str = DIRECT,
        cache_seconds: int = 300,
        token: TokenProvider | None = None,
        client: httpx.AsyncClient | None = None,
        clock: Callable[[], float] = time.monotonic,
        quota_project: str | None = None,
    ) -> None:
        if mode not in (DIRECT, TRANSITIVE):
            raise ValueError(f"unknown group lookup mode {mode!r}")
        self.mode = mode
        self.cache_seconds = cache_seconds
        self._token = token or adc_token_provider()
        self._client = client or httpx.AsyncClient(timeout=10.0)
        self._clock = clock
        self._quota_project = quota_project
        self._users: dict[tuple[str, frozenset[str]], tuple[float, frozenset[str]]] = {}
        self._group_names: dict[str, str] = {}  # group email -> groups/<id>; never changes

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
            except (LookupFailed, httpx.HTTPError) as exc:
                log.warning("group search failed (%s): no groups for this request", _what(exc))
                return frozenset()
        if complete and self.cache_seconds > 0:  # a failed lookup is asked again next time
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
        response = await self._get("groups:lookup", {"groupKey.id": group})
        if response.status_code == 404:
            log.warning("group %s not found in Cloud Identity", group)
            return None
        if response.status_code != 200:  # 403 also means "no group with this address"
            raise LookupFailed(f"groups:lookup HTTP {response.status_code}")
        name = response.json().get("name")
        if not name:
            raise LookupFailed("groups:lookup returned no name")
        self._group_names[group] = name
        return name

    async def _is_member(self, group: str, email: str) -> bool | None:
        """Membership in one group; None when the lookup failed."""
        try:
            name = await self._group_name(group)
            if not name:
                return False
            response = await self._get(f"{name}/memberships:lookup", {"memberKey.id": email})
            if response.status_code == 404:
                return False
            if response.status_code != 200:
                raise LookupFailed(f"memberships:lookup HTTP {response.status_code}")
            return True
        except (LookupFailed, httpx.HTTPError) as exc:
            log.warning("group lookup failed for %s (%s): nothing from this group for this request", group, _what(exc))
            return None

    async def _direct(self, email: str, wanted: frozenset[str]) -> tuple[frozenset[str], bool]:
        ordered = sorted(wanted)
        found = await asyncio.gather(*(self._is_member(g, email) for g in ordered))
        return frozenset(g for g, member in zip(ordered, found, strict=True) if member), None not in found

    async def _transitive(self, email: str, wanted: frozenset[str]) -> frozenset[str]:
        if "'" in email or "\\" in email:
            raise LookupFailed("unexpected character in email")
        query = f"member_key_id == '{email}' && '{_LABEL}' in labels"
        groups: set[str] = set()
        page = ""
        while True:
            params = {"query": query, **({"pageToken": page} if page else {})}
            response = await self._get("groups/-/memberships:searchTransitiveGroups", params)
            if response.status_code != 200:
                raise LookupFailed(f"searchTransitiveGroups HTTP {response.status_code}")
            body = response.json()
            groups.update(str(m.get("groupKey", {}).get("id", "")).lower() for m in body.get("memberships", []))
            page = body.get("nextPageToken", "")
            if not page:
                return frozenset(groups) & wanted


def _what(exc: Exception) -> str:
    return str(exc) if isinstance(exc, LookupFailed) else type(exc).__name__
