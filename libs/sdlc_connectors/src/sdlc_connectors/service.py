"""User connections (version-01 §4.3-4.5): connect, disconnect, status, and credentials for tools.

- connect: verify the PAT with the provider (identity, token type), take the expiry the provider
  reports (GitHub) or the one the user enters, refuse tokens that expire after the connection's
  `max_token_days`, then write the user's directory.
- Writes are serialised per user: `lock(key)` (an async context manager; the MCP server combines a
  process lock with a Postgres advisory lock), then re-read, change, save.
- credential: the tool's view. Missing, expired or provider-rejected connections raise
  NotConnected; there is never a fallback to a service credential. Values are cached for 5 min
  per (user, connection); every write drops the user's cache.
- Callers authorize first: the MCP policy check runs before a tool ever asks for a credential.
"""

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta

from sdlc_config.model import ConnectionDef, Snapshot

from sdlc_connectors import providers
from sdlc_connectors.errors import ConnectorError
from sdlc_connectors.user_store import (
    ConnectionEntry,
    UserDirectory,
    UserSecretStore,
    user_key,
)

CACHE_TTL = 300.0
EXPIRY_WARNING_DAYS = 14


class NotConnected(ConnectorError):
    def __init__(self, connection: str, reason: str) -> None:
        super().__init__(f"{connection}: {reason}")
        self.connection, self.reason = connection, reason


class ConnectError(ConnectorError):
    """The token cannot be stored (rejected, wrong type, expiry missing or too far out)."""


@dataclass(frozen=True)
class Credential:
    connection: ConnectionDef
    token: str
    username: str | None

    def __repr__(self) -> str:
        return f"Credential(connection={self.connection.id!r}, token=***)"


def process_locks() -> Callable[[str], AbstractAsyncContextManager[None]]:
    """Per-key asyncio locks (one process). Multi-instance deployments add a DB advisory lock."""
    locks: dict[str, asyncio.Lock] = {}

    @asynccontextmanager
    async def lock(key: str) -> AsyncIterator[None]:
        async with locks.setdefault(key, asyncio.Lock()):
            yield

    return lock


def _now() -> datetime:
    return datetime.now(UTC)


class ConnectionService:
    def __init__(
        self,
        store: UserSecretStore,
        snapshot: Callable[[], Snapshot],
        lock: Callable[[str], AbstractAsyncContextManager[None]] | None = None,
        *,
        verify=providers.verify,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.store = store
        self._snapshot = snapshot
        self._lock = lock or process_locks()
        self._verify = verify
        self._clock = clock
        self._cache: dict[tuple[str, str], tuple[float, UserDirectory | None]] = {}

    def catalog(self) -> dict[str, ConnectionDef]:
        return dict(self._snapshot().connections)

    def _conn(self, connection_id: str) -> ConnectionDef:
        conn = self.catalog().get(connection_id)
        if conn is None:
            raise ConnectError(f"unknown connection '{connection_id}'")
        return conn

    async def _load(self, oid: str) -> UserDirectory | None:
        return await asyncio.to_thread(self.store.load, oid)

    async def _cached(self, oid: str) -> UserDirectory | None:
        key = (oid, "dir")
        hit = self._cache.get(key)
        if hit and hit[0] > self._clock():
            return hit[1]
        directory = await self._load(oid)
        self._cache[key] = (self._clock() + CACHE_TTL, directory)
        return directory

    def _drop(self, oid: str) -> None:
        self._cache.pop((oid, "dir"), None)

    # --- the Connections page ---------------------------------------------------------------

    async def status(self, oid: str) -> list[dict]:
        directory = await self._load(oid) or UserDirectory(oid)
        today = _now().date()
        out = []
        for conn in self.catalog().values():
            entry = directory.connections.get(conn.id)
            item = {
                "id": conn.id,
                "provider": conn.provider,
                "edition": conn.edition,
                "description": conn.description,
                "token_help": conn.token_help,
                "needs_username": conn.needs_username,
                "max_token_days": conn.max_token_days,
                "connected": entry is not None,
            }
            if entry is not None:
                item.update(entry.public())
                expires = date.fromisoformat(entry.expires_at) if entry.expires_at else None
                item["expired"] = bool(expires and expires < today)
                item["expiring_soon"] = bool(
                    expires and today <= expires <= today + timedelta(days=EXPIRY_WARNING_DAYS)
                )
            out.append(item)
        return out

    async def connect(
        self,
        oid: str,
        connection_id: str,
        token: str,
        username: str | None = None,
        expires_at: date | None = None,
    ) -> dict:
        conn = self._conn(connection_id)
        username = (username or "").strip() or None
        if conn.needs_username and not username:
            raise ConnectError("this connection needs your account email with the token")
        try:
            account = await asyncio.to_thread(self._verify, conn, token.strip(), username)
        except providers.TokenRejected as e:
            raise ConnectError(str(e)) from None
        expiry = account.expires_at or expires_at
        today = _now().date()
        if expiry is None:
            raise ConnectError("enter the token's expiry date (tokens must expire)")
        if expiry < today:
            raise ConnectError("the token has already expired")
        if expiry > today + timedelta(days=conn.max_token_days):
            raise ConnectError(
                f"the token must expire within {conn.max_token_days} days; "
                "create a shorter-lived one"
            )
        now = _now().isoformat(timespec="seconds")
        entry = ConnectionEntry(
            token=token.strip(),
            account=account.account,
            display=account.display,
            connected_at=now,
            verified_at=now,
            username=username,
            expires_at=expiry.isoformat(),
        )
        async with self._lock(user_key(oid)):
            directory = await self._load(oid) or UserDirectory(oid)
            directory.connections[conn.id] = entry
            await asyncio.to_thread(self.store.save, directory)
            self._drop(oid)
        return {"id": conn.id, "connected": True, **entry.public()}

    async def disconnect(self, oid: str, connection_id: str) -> bool:
        async with self._lock(user_key(oid)):
            directory = await self._load(oid)
            if directory is None or connection_id not in directory.connections:
                return False
            del directory.connections[connection_id]
            if directory.connections:
                await asyncio.to_thread(self.store.save, directory)
            else:
                await asyncio.to_thread(self.store.delete, oid)
            self._drop(oid)
        return True

    async def forget_user(self, oid: str) -> None:
        """Offboarding / blocked users: delete the whole directory."""
        async with self._lock(user_key(oid)):
            await asyncio.to_thread(self.store.delete, oid)
            self._drop(oid)

    # --- tools ------------------------------------------------------------------------------

    async def credential(self, oid: str, connection_id: str) -> Credential:
        conn = self.catalog().get(connection_id)
        if conn is None:
            raise NotConnected(connection_id, "this connection is not configured")
        directory = await self._cached(oid)
        entry = directory.connections.get(conn.id) if directory else None
        if entry is None:
            raise NotConnected(conn.id, "not connected")
        if entry.status != "ok":
            raise NotConnected(conn.id, "the provider rejected the saved token; connect again")
        if entry.expires_at and date.fromisoformat(entry.expires_at) < _now().date():
            raise NotConnected(conn.id, "the saved token has expired; connect again")
        return Credential(conn, entry.token, entry.username)

    async def mark_invalid(self, oid: str, connection_id: str) -> None:
        """The provider answered 401/403 for the saved token (revoked, rotated, scopes)."""
        async with self._lock(user_key(oid)):
            directory = await self._load(oid)
            entry = directory.connections.get(connection_id) if directory else None
            if entry is None:
                return
            directory.connections[connection_id] = replace(entry, status="invalid")
            await asyncio.to_thread(self.store.save, directory)
            self._drop(oid)
