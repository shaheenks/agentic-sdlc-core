"""Per-user secret directory (version-01 §4.3): one secret per user holding all their connections.

  {"schema": 1, "oid": "<entra oid>", "connections": {"<connection id>": {token, username, ...}}}

- The key is the first 32 hex characters of SHA-256(oid), so a listing does not show user ids.
- The `oid` inside is checked on every read: a misnamed or swapped secret fails closed.
- Backends: MemoryUserStore (tests), FileUserStore (local dev: one Fernet-encrypted file per user
  on an MCP-only volume), GcpUserStore (Secret Manager: secret `sdlc-<env>-user-<key>`, a new
  version per write, older versions destroyed).
- Stores are synchronous and hold no locks: ConnectionService serialises writes per user.
- Entries never print their token (masked repr).
"""

import base64
import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

import httpx

from sdlc_connectors.errors import ConnectorError

SCHEMA = 1


def user_key(oid: str) -> str:
    return hashlib.sha256(oid.lower().encode()).hexdigest()[:32]


class UserStoreError(ConnectorError):
    pass


@dataclass(frozen=True)
class ConnectionEntry:
    token: str
    account: str
    display: str
    connected_at: str
    verified_at: str
    username: str | None = None
    expires_at: str | None = None  # ISO date
    status: str = "ok"  # ok | invalid (the provider rejected it since)

    def __repr__(self) -> str:
        return f"ConnectionEntry(account={self.account!r}, status={self.status!r}, token=***)"

    def public(self) -> dict:
        """What the Connections page may see: never the token."""
        return {
            "account": self.account,
            "display": self.display,
            "username": self.username,
            "expires_at": self.expires_at,
            "connected_at": self.connected_at,
            "status": self.status,
        }


@dataclass
class UserDirectory:
    oid: str
    connections: dict[str, ConnectionEntry] = field(default_factory=dict)

    def to_json(self) -> bytes:
        return json.dumps(
            {
                "schema": SCHEMA,
                "oid": self.oid,
                "connections": {k: asdict(v) for k, v in self.connections.items()},
            },
            sort_keys=True,
        ).encode()

    @classmethod
    def from_json(cls, raw: bytes, expected_oid: str) -> "UserDirectory":
        try:
            doc = json.loads(raw)
            if doc.get("schema") != SCHEMA:
                raise UserStoreError("unknown user-secret schema")
            if str(doc.get("oid", "")).lower() != expected_oid.lower():
                raise UserStoreError("user-secret owner mismatch")  # fail closed
            entries = {k: ConnectionEntry(**v) for k, v in doc.get("connections", {}).items()}
        except (ValueError, TypeError, AttributeError) as e:
            raise UserStoreError(f"unreadable user secret ({type(e).__name__})") from None
        return cls(doc["oid"], entries)


class UserSecretStore(Protocol):
    name: str

    def load(self, oid: str) -> UserDirectory | None: ...

    def save(self, directory: UserDirectory) -> None: ...

    def delete(self, oid: str) -> None: ...


class MemoryUserStore:
    name = "memory"

    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    def load(self, oid):
        raw = self.data.get(user_key(oid))
        return UserDirectory.from_json(raw, oid) if raw else None

    def save(self, directory):
        self.data[user_key(directory.oid)] = directory.to_json()

    def delete(self, oid):
        self.data.pop(user_key(oid), None)


class FileUserStore:
    """Local dev: `<root>/<key>.bin`, Fernet-encrypted with SDLC_USER_SECRETS_KEY."""

    name = "file"

    def __init__(self, root: Path, key: str) -> None:
        from cryptography.fernet import Fernet

        try:
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except (ValueError, TypeError):
            raise UserStoreError("SDLC_USER_SECRETS_KEY is not a valid Fernet key") from None
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, oid: str) -> Path:
        return self.root / f"{user_key(oid)}.bin"

    def load(self, oid):
        from cryptography.fernet import InvalidToken

        path = self._path(oid)
        if not path.is_file():
            return None
        try:
            raw = self._fernet.decrypt(path.read_bytes())
        except InvalidToken:
            raise UserStoreError("user secret cannot be decrypted (wrong key?)") from None
        return UserDirectory.from_json(raw, oid)

    def save(self, directory):
        path = self._path(directory.oid)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(self._fernet.encrypt(directory.to_json()))
        os.replace(tmp, path)  # atomic: a reader never sees half a file

    def delete(self, oid):
        self._path(oid).unlink(missing_ok=True)


class GcpUserStore:
    """Secret Manager: `sdlc-<env>-user-<key>` (regional when `location` is set). Writes add a
    version and destroy all but the newest two; delete removes the secret."""

    name = "gcp"

    def __init__(
        self,
        project: str,
        env: str,
        location: str | None = None,
        *,
        token_provider: Callable[[], str] | None = None,
        transport: httpx.BaseTransport | None = None,
        quota_project: str | None = None,
    ) -> None:
        self.project, self.env, self.location = project, env, location
        self._token = token_provider
        self._quota = quota_project
        self._client = httpx.Client(transport=transport, timeout=15.0, follow_redirects=False)

    def _host(self) -> str:
        if self.location:  # regional secret: regional endpoint
            return f"https://secretmanager.{self.location}.rep.googleapis.com"
        return "https://secretmanager.googleapis.com"

    def _base(self) -> str:
        parent = f"projects/{self.project}"
        if self.location:
            parent += f"/locations/{self.location}"
        return f"{self._host()}/v1/{parent}"

    def secret_id(self, oid: str) -> str:
        return f"sdlc-{self.env}-user-{user_key(oid)}"

    def _headers(self) -> dict[str, str]:
        if self._token is None:
            from sdlc_secrets.stores import adc_token_provider

            self._token = adc_token_provider()
        headers = {"Authorization": f"Bearer {self._token()}"}
        if self._quota:
            headers["x-goog-user-project"] = self._quota
        return headers

    def _call(self, method: str, url: str, **kw) -> httpx.Response:
        try:
            response = self._client.request(method, url, headers=self._headers(), **kw)
        except httpx.HTTPError as e:
            raise UserStoreError(f"Secret Manager unreachable ({type(e).__name__})") from None
        return response

    def load(self, oid):
        url = f"{self._base()}/secrets/{self.secret_id(oid)}/versions/latest:access"
        response = self._call("GET", url)
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise UserStoreError(f"Secret Manager returned {response.status_code} on read")
        raw = base64.b64decode(response.json()["payload"]["data"])
        return UserDirectory.from_json(raw, oid)

    def save(self, directory):
        sid = self.secret_id(directory.oid)
        add = self._call(
            "POST",
            f"{self._base()}/secrets/{sid}:addVersion",
            json={"payload": {"data": base64.b64encode(directory.to_json()).decode()}},
        )
        if add.status_code == 404:  # first connect: create the secret, then add the version
            body: dict = {"labels": {"kind": "user-connections", "env": self.env}}
            if not self.location:
                body["replication"] = {"automatic": {}}
            created = self._call(
                "POST", f"{self._base()}/secrets", params={"secretId": sid}, json=body
            )
            if created.status_code not in (200, 409):
                raise UserStoreError(f"Secret Manager returned {created.status_code} on create")
            return self.save(directory)
        if add.status_code != 200:
            raise UserStoreError(f"Secret Manager returned {add.status_code} on write")
        self._destroy_old_versions(sid)

    def _destroy_old_versions(self, sid: str, keep: int = 2) -> None:
        listing = self._call(
            "GET",
            f"{self._base()}/secrets/{sid}/versions",
            params={"filter": "state:ENABLED OR state:DISABLED"},
        )
        if listing.status_code != 200:
            return  # cleanup is best effort; the next write retries it
        versions = sorted(
            listing.json().get("versions", []),
            key=lambda v: int(v["name"].rsplit("/", 1)[-1]),
            reverse=True,
        )
        for version in versions[keep:]:  # version["name"] is the full resource name
            self._call("POST", f"{self._host()}/v1/{version['name']}:destroy", json={})

    def delete(self, oid):
        response = self._call("DELETE", f"{self._base()}/secrets/{self.secret_id(oid)}")
        if response.status_code not in (200, 404):
            raise UserStoreError(f"Secret Manager returned {response.status_code} on delete")


def store_from_env(environ=None) -> UserSecretStore | None:
    """SDLC_USER_SECRETS_BACKEND = file (SDLC_USER_SECRETS_DIR + SDLC_USER_SECRETS_KEY) | gcp
    (SDLC_SECRETS_PROJECT, SDLC_SECRETS_LOCATION, SDLC_ENV) | memory (tests) | unset = off."""
    environ = os.environ if environ is None else environ
    backend = environ.get("SDLC_USER_SECRETS_BACKEND", "")
    if not backend:
        return None
    if backend == "memory":
        return MemoryUserStore()
    if backend == "file":
        key = environ.get("SDLC_USER_SECRETS_KEY", "")
        if not key:
            raise UserStoreError("SDLC_USER_SECRETS_BACKEND=file needs SDLC_USER_SECRETS_KEY")
        return FileUserStore(Path(environ.get("SDLC_USER_SECRETS_DIR", "/data/user-secrets")), key)
    if backend == "gcp":
        project = environ.get("SDLC_SECRETS_PROJECT") or environ.get("GOOGLE_CLOUD_PROJECT", "")
        if not project:
            raise UserStoreError("SDLC_USER_SECRETS_BACKEND=gcp needs SDLC_SECRETS_PROJECT")
        return GcpUserStore(
            project,
            environ.get("SDLC_ENV", "local"),
            environ.get("SDLC_SECRETS_LOCATION") or None,
            quota_project=environ.get("GOOGLE_CLOUD_QUOTA_PROJECT") or None,
        )
    raise UserStoreError(f"unknown SDLC_USER_SECRETS_BACKEND '{backend}'")


__all__ = [
    "ConnectionEntry",
    "FileUserStore",
    "GcpUserStore",
    "MemoryUserStore",
    "UserDirectory",
    "UserSecretStore",
    "UserStoreError",
    "store_from_env",
    "user_key",
]
