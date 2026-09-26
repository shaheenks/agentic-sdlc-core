"""Group membership resolution, including the Entra "groups overage" fallback.

When a user is in too many groups, Entra omits the `groups` claim and sets `_claim_names`.
We then ask Microsoft Graph (transitiveMemberOf) using the MCP server's own app credential.
Requires the application permission GroupMember.Read.All with admin consent.
If no resolver is configured, an overage user gets NO groups (fail closed).
"""

import asyncio
import re
import time
from typing import Literal, Protocol

import httpx

from sdlc_auth.principal import Principal

_GUID = re.compile(r"^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")

GroupSource = Literal["token", "graph", "overage_unresolved"]


class GroupResolver(Protocol):
    async def resolve(self, principal: Principal) -> frozenset[str]: ...


async def effective_group_ids(
    principal: Principal, resolver: GroupResolver | None
) -> tuple[frozenset[str], GroupSource]:
    if not principal.groups_overage:
        return principal.group_ids, "token"
    if resolver is None:
        return frozenset(), "overage_unresolved"
    return await resolver.resolve(principal), "graph"


class GraphGroupResolver:
    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        ttl_seconds: int = 600,
        http: httpx.AsyncClient | None = None,
        graph_base: str = "https://graph.microsoft.com/v1.0",
        login_base: str = "https://login.microsoftonline.com",
    ):
        self._tenant_id, self._client_id, self._secret = tenant_id, client_id, client_secret
        self._ttl = ttl_seconds
        self._http = http or httpx.AsyncClient(timeout=10)
        self._graph, self._login = graph_base.rstrip("/"), login_base.rstrip("/")
        self._app_token: tuple[str, float] | None = None  # (token, expires_at)
        self._cache: dict[str, tuple[frozenset[str], float]] = {}
        self._lock = asyncio.Lock()

    async def resolve(self, principal: Principal) -> frozenset[str]:
        if not _GUID.match(principal.oid):
            raise ValueError("principal oid is not a GUID")
        now = time.monotonic()
        cached = self._cache.get(principal.oid)
        if cached and cached[1] > now:
            return cached[0]
        headers = {"Authorization": f"Bearer {await self._get_app_token()}"}
        url: str | None = (
            f"{self._graph}/users/{principal.oid}/transitiveMemberOf/microsoft.graph.group"
            "?$select=id&$top=999"
        )
        ids: set[str] = set()
        while url:
            resp = await self._http.get(url, headers=headers)
            resp.raise_for_status()
            body = resp.json()
            ids.update(item["id"].lower() for item in body.get("value", []))
            url = body.get("@odata.nextLink")
        result = frozenset(ids)
        self._cache[principal.oid] = (result, now + self._ttl)
        return result

    async def _get_app_token(self) -> str:
        async with self._lock:
            if self._app_token and self._app_token[1] > time.monotonic() + 60:
                return self._app_token[0]
            resp = await self._http.post(
                f"{self._login}/{self._tenant_id}/oauth2/v2.0/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._secret,
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            resp.raise_for_status()
            body = resp.json()
            self._app_token = (body["access_token"], time.monotonic() + int(body["expires_in"]))
            return self._app_token[0]
