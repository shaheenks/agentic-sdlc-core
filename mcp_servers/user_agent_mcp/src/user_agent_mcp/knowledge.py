"""The proxy to Knowledge Search (NFR-ARCH-004, FR-KNOW-002; DEC-0011).

user_agent_mcp runs no knowledge query itself and holds no store credentials. It sends each query with the
filter attribute it computed from the caller's effective policy, and proves itself to Knowledge Search with
its own service account's Google ID token (from the metadata server), never the user's."""

import base64
import json
import time
from typing import Any

import httpx

from user_agent_mcp.errors import ToolError

METADATA_IDENTITY = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity"
REFRESH_BEFORE = 300  # seconds before expiry


def _expiry(token: str) -> float:
    try:
        payload = token.split(".")[1]
        return float(json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["exp"])
    except (IndexError, KeyError, ValueError):
        return 0.0


class KnowledgeClient:
    def __init__(self, url: str, auth: str = "id_token", http: httpx.AsyncClient | None = None) -> None:
        self.url = url.rstrip("/")
        self.auth = auth
        self.http = http or httpx.AsyncClient(timeout=20)
        self._token: tuple[str, float] | None = None

    async def _id_token(self) -> str:
        if self._token and self._token[1] - REFRESH_BEFORE > time.time():
            return self._token[0]
        response = await self.http.get(
            METADATA_IDENTITY,
            params={"audience": self.url, "format": "full"},
            headers={"Metadata-Flavor": "Google"},
        )
        response.raise_for_status()
        token = response.text.strip()
        self._token = (token, _expiry(token))
        return token

    async def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            headers = {"Authorization": f"Bearer {await self._id_token()}"} if self.auth == "id_token" else {}
            response = await self.http.post(f"{self.url}{path}", json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise ToolError("knowledge_unavailable", "knowledge search is unavailable; try again later") from exc
        if response.status_code == 200:
            return response.json()
        try:
            error = response.json()
        except ValueError:
            error = {}
        if response.status_code == 400 and error.get("error") == "invalid_argument":
            raise ToolError("invalid_argument", str(error.get("message") or "invalid argument"))
        raise ToolError("knowledge_unavailable", "knowledge search is unavailable; try again later")
