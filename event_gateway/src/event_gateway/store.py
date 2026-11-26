"""Deliveries and runs, under `events/` of a bucket (DEC-0003): one object per delivery, created only if absent, so a
redelivered event starts at most one run (FR-TRIG-001); and one object per run with its session, so a retried task
continues the same run. Deleted after 7 days by the bucket's lifecycle."""

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

import httpx

NAME = re.compile(r"^[A-Za-z0-9._/-]{1,400}$")
STORAGE = "https://storage.googleapis.com"


def _check(name: str) -> str:
    if not NAME.match(name) or ".." in name:
        raise ValueError(f"not an event object name: {name!r}")
    return name


class EventStore(Protocol):
    async def claim(self, name: str, value: dict[str, Any]) -> bool: ...
    async def read(self, name: str) -> dict[str, Any] | None: ...
    async def write(self, name: str, value: dict[str, Any]) -> None: ...


class DirStore:
    """A folder, for the local environment and tests."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, name: str) -> Path:
        path = self.root / "events" / _check(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    async def claim(self, name: str, value: dict[str, Any]) -> bool:
        try:
            fd = os.open(self._path(name), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f)
        return True

    async def read(self, name: str) -> dict[str, Any] | None:
        path = self._path(name)
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    async def write(self, name: str, value: dict[str, Any]) -> None:
        self._path(name).write_text(json.dumps(value), encoding="utf-8")


class GcsStore:
    """Objects under `events/` of a bucket, through the Cloud Storage JSON API with the service's own identity."""

    def __init__(self, bucket: str, client: httpx.AsyncClient | None = None, credentials=None) -> None:
        self.bucket = bucket
        self.client = client or httpx.AsyncClient(timeout=15)
        self._credentials = credentials

    async def _headers(self) -> dict[str, str]:
        if self._credentials is None:
            import google.auth

            self._credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/devstorage.read_write"])
        if not self._credentials.valid:
            import google.auth.transport.requests

            await asyncio.to_thread(self._credentials.refresh, google.auth.transport.requests.Request())
        return {"Authorization": f"Bearer {self._credentials.token}"}

    async def _upload(self, name: str, value: dict[str, Any], only_if_absent: bool) -> bool:
        params = {"uploadType": "media", "name": f"events/{_check(name)}"}
        if only_if_absent:
            params["ifGenerationMatch"] = "0"
        response = await self.client.post(
            f"{STORAGE}/upload/storage/v1/b/{self.bucket}/o",
            params=params,
            content=json.dumps(value).encode(),
            headers={**await self._headers(), "Content-Type": "application/json"},
        )
        if only_if_absent and response.status_code == 412:  # the object exists: claimed before
            return False
        response.raise_for_status()
        return True

    async def claim(self, name: str, value: dict[str, Any]) -> bool:
        return await self._upload(name, value, only_if_absent=True)

    async def read(self, name: str) -> dict[str, Any] | None:
        response = await self.client.get(
            f"{STORAGE}/storage/v1/b/{self.bucket}/o/{quote(f'events/{_check(name)}', safe='')}",
            params={"alt": "media"},
            headers=await self._headers(),
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def write(self, name: str, value: dict[str, Any]) -> None:
        await self._upload(name, value, only_if_absent=False)
