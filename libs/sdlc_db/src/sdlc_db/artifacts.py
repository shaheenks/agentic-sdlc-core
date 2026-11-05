"""Artifact metadata (version-03 P5, db/migrations/005_artifacts.sql), owner only.

Every query runs inside `owner_scoped(conn, oid)`, which sets `app.user_oid` for one transaction;
the table's RLS policy filters and checks every row on it, so a bug here cannot reach another
user's rows. The oid must come from the verified token, never from tool arguments.
"""

import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime

from psycopg import AsyncConnection

_OID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def normalize_oid(oid: str) -> str:
    value = (oid or "").strip().lower()
    if not _OID.match(value):
        raise ValueError("invalid user oid")
    return value


@asynccontextmanager
async def owner_scoped(conn: AsyncConnection, oid: str) -> AsyncIterator[AsyncConnection]:
    """One transaction in which the caller sees and writes only rows they own."""
    owner = normalize_oid(oid)
    async with conn.transaction():
        await conn.execute("SELECT set_config('app.user_oid', %s, true)", (owner,))
        yield conn


@dataclass(frozen=True)
class ArtifactRow:
    id: str
    name: str
    media_type: str
    size_bytes: int
    sha256: str
    created_at: datetime
    expires_at: datetime

    def public(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }


def parse_id(artifact_id: str) -> str | None:
    """Canonical uuid text, or None for anything that is not one (answered as "not found")."""
    try:
        return str(uuid.UUID(str(artifact_id)))
    except ValueError:
        return None


async def delete_expired(conn: AsyncConnection) -> list[str]:
    """Remove the caller's expired rows; returns their ids (content goes by the store's lifecycle
    or the caller deletes it)."""
    cur = await conn.execute("DELETE FROM artifacts WHERE expires_at <= now() RETURNING id::text")
    return [r[0] for r in await cur.fetchall()]


async def count_live(conn: AsyncConnection) -> int:
    cur = await conn.execute("SELECT count(*) FROM artifacts WHERE expires_at > now()")
    return (await cur.fetchone())[0]


async def insert(
    conn: AsyncConnection,
    *,
    artifact_id: str,
    owner_oid: str,
    name: str,
    media_type: str,
    size_bytes: int,
    sha256: str,
    agent_session_id: str | None,
    retention_days: float,
) -> ArtifactRow:
    cur = await conn.execute(
        """
        INSERT INTO artifacts (id, owner_oid, name, media_type, size_bytes, sha256,
                               agent_session_id, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, now() + make_interval(secs => %s))
        RETURNING id::text, name, media_type, size_bytes, sha256, created_at, expires_at
        """,
        (
            artifact_id,
            normalize_oid(owner_oid),
            name,
            media_type,
            size_bytes,
            sha256,
            agent_session_id,
            retention_days * 86400,
        ),
    )
    return ArtifactRow(*await cur.fetchone())


async def list_live(conn: AsyncConnection) -> list[ArtifactRow]:
    cur = await conn.execute(
        "SELECT id::text, name, media_type, size_bytes, sha256, created_at, expires_at"
        " FROM artifacts WHERE expires_at > now() ORDER BY created_at DESC"
    )
    return [ArtifactRow(*r) for r in await cur.fetchall()]


async def get_live(conn: AsyncConnection, artifact_id: str) -> ArtifactRow | None:
    key = parse_id(artifact_id)
    if key is None:
        return None
    cur = await conn.execute(
        "SELECT id::text, name, media_type, size_bytes, sha256, created_at, expires_at"
        " FROM artifacts WHERE id = %s AND expires_at > now()",
        (key,),
    )
    row = await cur.fetchone()
    return ArtifactRow(*row) if row else None


async def delete(conn: AsyncConnection, artifact_id: str) -> bool:
    key = parse_id(artifact_id)
    if key is None:
        return False
    cur = await conn.execute("DELETE FROM artifacts WHERE id = %s RETURNING id", (key,))
    return await cur.fetchone() is not None
