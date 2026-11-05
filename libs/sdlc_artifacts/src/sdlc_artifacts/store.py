"""Artifact content stores. Keys are `artifacts/<owner oid>/<artifact id>`, built here from values
the MCP server has already checked (oid from the token, id = a new uuid), never from user input.

SDLC_ARTIFACT_STORE selects the backend:
  file:///data/artifacts         local dev (compose volume mounted only by core-mcp)
  gs://<bucket>[/<prefix>]       GCP (the MCP service account has objectUser on the bucket)
  (empty)                        artifacts off: the tools answer "not configured"
The GCS bucket's lifecycle deletes objects after its retention; deletes here are best effort.
"""

import os
import re
import uuid
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

import httpx

_OID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
GCS_API = "https://storage.googleapis.com"  # fixed endpoint: no config can redirect it


class ArtifactStoreError(RuntimeError):
    """The store could not be reached or refused the operation (details are logged, not shown)."""


def object_key(owner_oid: str, artifact_id: str) -> str:
    oid = owner_oid.lower()
    if not _OID.match(oid):
        raise ValueError("invalid owner oid")
    return f"artifacts/{oid}/{uuid.UUID(artifact_id)}"


class ArtifactStore(Protocol):
    name: str

    def put(self, key: str, data: bytes, media_type: str) -> None: ...

    def get(self, key: str) -> bytes | None: ...

    def delete(self, key: str) -> None: ...


class MemoryArtifactStore:
    name = "memory"

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key, data, media_type):
        self.objects[key] = data

    def get(self, key):
        return self.objects.get(key)

    def delete(self, key):
        self.objects.pop(key, None)


class FileArtifactStore:
    """Local dev: one file per artifact under `root`."""

    name = "file"

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ArtifactStoreError("key outside the store")
        return path

    def put(self, key, data, media_type):
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    def get(self, key):
        path = self._path(key)
        return path.read_bytes() if path.is_file() else None

    def delete(self, key):
        self._path(key).unlink(missing_ok=True)


class GcsArtifactStore:
    """Cloud Storage JSON API with the service identity (ADC)."""

    name = "gcs"

    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        *,
        token_provider=None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.bucket = bucket
        self.prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""
        self._token = token_provider
        self._client = httpx.Client(transport=transport, timeout=30.0, follow_redirects=False)

    def _headers(self) -> dict[str, str]:
        if self._token is None:
            from sdlc_secrets.stores import adc_token_provider

            self._token = adc_token_provider()
        return {"Authorization": f"Bearer {self._token()}"}

    def _object(self, key: str) -> str:
        return quote(self.prefix + key, safe="")

    def _call(self, method: str, url: str, **kw) -> httpx.Response:
        try:
            return self._client.request(
                method, url, headers=self._headers() | kw.pop("headers", {}), **kw
            )
        except httpx.HTTPError as e:
            raise ArtifactStoreError(f"artifact store unreachable ({type(e).__name__})") from None

    def put(self, key, data, media_type):
        url = f"{GCS_API}/upload/storage/v1/b/{self.bucket}/o"
        params = {"uploadType": "media", "name": self.prefix + key, "ifGenerationMatch": "0"}
        r = self._call(
            "POST", url, params=params, content=data, headers={"Content-Type": media_type}
        )
        if r.status_code >= 300:
            raise ArtifactStoreError(f"artifact upload failed: HTTP {r.status_code}")

    def get(self, key):
        url = f"{GCS_API}/storage/v1/b/{self.bucket}/o/{self._object(key)}"
        r = self._call("GET", url, params={"alt": "media"})
        if r.status_code == 404:
            return None
        if r.status_code >= 300:
            raise ArtifactStoreError(f"artifact download failed: HTTP {r.status_code}")
        return r.content

    def delete(self, key):
        url = f"{GCS_API}/storage/v1/b/{self.bucket}/o/{self._object(key)}"
        r = self._call("DELETE", url)
        if r.status_code not in (204, 200, 404):
            raise ArtifactStoreError(f"artifact delete failed: HTTP {r.status_code}")


def store_from_env(environ=os.environ) -> ArtifactStore | None:
    location = environ.get("SDLC_ARTIFACT_STORE", "").strip()
    if not location:
        return None
    if location.startswith("file://"):
        return FileArtifactStore(Path(location[len("file://") :]))
    if location.startswith("gs://"):
        bucket, _, prefix = location[len("gs://") :].partition("/")
        if not bucket:
            raise ValueError("SDLC_ARTIFACT_STORE: no bucket in gs:// location")
        return GcsArtifactStore(bucket, prefix)
    raise ValueError("SDLC_ARTIFACT_STORE must start with file:// or gs://")
