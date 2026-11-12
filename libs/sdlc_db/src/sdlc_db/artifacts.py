"""Artifact metadata (version-03 P5, db/migrations/005_artifacts.sql), owner only.

Every query runs inside `owner_scoped(conn, oid)`, which sets `app.user_oid` for one transaction;
the table's RLS policy filters and checks every row on it, so a bug here cannot reach another
user's rows. The oid must come from the verified token, never from tool arguments.

Versions (migration 006): a document has a stable `document_id`; each save that replaces it adds
an immutable row with the next `version`. `id` is the row's own id (the content's object key).
Callers address documents by `document_id` (the public "id"), optionally with a version.
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
    row_id: str  # this version's own id: the object key of its content
    document_id: str  # the stable, public id of the document
    version: int
    name: str
    media_type: str
    size_bytes: int
    sha256: str
    created_at: datetime
    expires_at: datetime
    versions: int = 1  # live versions of the document (set by list_live)

    def public(self) -> dict:
        return {
            "id": self.document_id,
            "version": self.version,
            "versions": self.versions,
            "name": self.name,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }


_SELECT = (
    "SELECT id::text, document_id::text, version, name, media_type, size_bytes, sha256,"
    " created_at, expires_at"
)


def parse_id(artifact_id: str) -> str | None:
    """Canonical uuid text, or None for anything that is not one (answered as "not found")."""
    try:
        return str(uuid.UUID(str(artifact_id)))
    except ValueError:
        return None


async def delete_expired(conn: AsyncConnection) -> list[str]:
    """Remove the caller's expired rows; returns their row ids (content goes by the store's
    lifecycle or the caller deletes it)."""
    cur = await conn.execute("DELETE FROM artifacts WHERE expires_at <= now() RETURNING id::text")
    return [r[0] for r in await cur.fetchall()]


async def count_live(conn: AsyncConnection) -> int:
    """The caller's live documents: a document counts once, however many versions it has."""
    cur = await conn.execute(
        "SELECT count(DISTINCT document_id) FROM artifacts WHERE expires_at > now()"
    )
    return (await cur.fetchone())[0]


async def count_versions(conn: AsyncConnection, document_id: str) -> int:
    """Live versions of one of the caller's documents (0: missing, expired or not theirs)."""
    key = parse_id(document_id)
    if key is None:
        return 0
    cur = await conn.execute(
        "SELECT count(*) FROM artifacts WHERE document_id = %s AND expires_at > now()", (key,)
    )
    return (await cur.fetchone())[0]


async def latest_version(conn: AsyncConnection, document_id: str) -> int | None:
    """Highest live version of the caller's document, or None (missing, expired, not theirs)."""
    key = parse_id(document_id)
    if key is None:
        return None
    cur = await conn.execute(
        "SELECT max(version) FROM artifacts WHERE document_id = %s AND expires_at > now()", (key,)
    )
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
    document_id: str | None = None,
    version: int = 1,
) -> ArtifactRow:
    """A new row: version 1 of a new document (document_id = its own id) or the next version."""
    cur = await conn.execute(
        """
        INSERT INTO artifacts (id, document_id, version, owner_oid, name, media_type, size_bytes,
                               sha256, agent_session_id, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now() + make_interval(secs => %s))
        RETURNING id::text, document_id::text, version, name, media_type, size_bytes, sha256,
                  created_at, expires_at
        """,
        (
            artifact_id,
            document_id or artifact_id,
            version,
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
    """The latest live version of each of the caller's documents, newest first."""
    cur = await conn.execute(
        "SELECT DISTINCT ON (document_id) id::text, document_id::text, version, name, media_type,"
        " size_bytes, sha256, created_at, expires_at,"
        " count(*) OVER (PARTITION BY document_id)"
        " FROM artifacts WHERE expires_at > now() ORDER BY document_id, version DESC"
    )
    rows = [ArtifactRow(*r) for r in await cur.fetchall()]
    return sorted(rows, key=lambda r: r.created_at, reverse=True)


async def get_live(
    conn: AsyncConnection, document_id: str, version: int | None = None
) -> ArtifactRow | None:
    """One version of the caller's document (the latest when `version` is None)."""
    key = parse_id(document_id)
    if key is None:
        return None
    if version is None:
        cur = await conn.execute(
            _SELECT + " FROM artifacts WHERE document_id = %s AND expires_at > now()"
            " ORDER BY version DESC LIMIT 1",
            (key,),
        )
    else:
        cur = await conn.execute(
            _SELECT + " FROM artifacts WHERE document_id = %s AND version = %s"
            " AND expires_at > now()",
            (key, version),
        )
    row = await cur.fetchone()
    return ArtifactRow(*row) if row else None


async def list_versions(conn: AsyncConnection, document_id: str) -> list[ArtifactRow]:
    """Live versions of the caller's document, newest first ([] if none)."""
    key = parse_id(document_id)
    if key is None:
        return []
    cur = await conn.execute(
        _SELECT + " FROM artifacts WHERE document_id = %s AND expires_at > now()"
        " ORDER BY version DESC",
        (key,),
    )
    return [ArtifactRow(*r) for r in await cur.fetchall()]


async def delete_document(conn: AsyncConnection, document_id: str) -> list[str]:
    """Delete every version of the caller's document; returns the deleted row ids."""
    key = parse_id(document_id)
    if key is None:
        return []
    cur = await conn.execute(
        "DELETE FROM artifacts WHERE document_id = %s RETURNING id::text", (key,)
    )
    return [r[0] for r in await cur.fetchall()]
