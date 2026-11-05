"""Artifact tools (version-03 P5, F1): the agent saves documents the user can download later.

Owner only: the owner is the caller's oid from the verified token, never a tool argument. Metadata
is in Postgres under row-level security on that oid (`sdlc_db.owner_scoped`); content is in the
artifact store under `artifacts/<oid>/<id>`. Another user's id, a malformed id and an expired
artifact all answer "artifact not found".

Audit: `artifact_change` (create/delete) and `artifact_access` (read), next to the `tool_call`
record; never the content or the file name.
"""

import asyncio
import hashlib
import logging
import uuid
from dataclasses import dataclass

from fastmcp.exceptions import ToolError
from sdlc_artifacts import (
    MAX_LIVE_PER_USER,
    ArtifactInputError,
    ArtifactStore,
    ArtifactStoreError,
    object_key,
    validate,
)
from sdlc_db import artifacts as db
from sdlc_db import owner_scoped

from sdlc_core_mcp.audit import audit_artifact
from sdlc_core_mcp.correlation import current_correlation
from sdlc_core_mcp.identity import Identity, request_identity
from sdlc_core_mcp.knowledge_tools import Knowledge

log = logging.getLogger("sdlc.mcp")
DOWNLOAD_PATH = "/artifacts/"  # served through oauth2-proxy (F2)
NOT_FOUND = "artifact not found"


@dataclass
class Artifacts:
    store: ArtifactStore | None
    knowledge: Knowledge | None  # its pool is the sdlc_app role (RLS)
    retention_days: float = 7.0

    @property
    def enabled(self) -> bool:
        return self.store is not None and self.knowledge is not None


def _public(row: db.ArtifactRow) -> dict:
    return {**row.public(), "download_path": f"{DOWNLOAD_PATH}{row.id}"}


def make_artifact_tools(artifacts: Artifacts) -> list:
    async def _begin() -> tuple[Identity, object]:
        ident = await request_identity()
        if not artifacts.enabled:
            raise ToolError("artifacts are not configured on this server")
        return ident, await artifacts.knowledge.open_pool()

    async def _drop_objects(oid: str, ids: list[str]) -> None:
        for artifact_id in ids:  # best effort: the store's lifecycle removes leftovers
            try:
                await asyncio.to_thread(artifacts.store.delete, object_key(oid, artifact_id))
            except ArtifactStoreError as e:
                log.warning("artifact content not deleted (%s): %s", artifact_id, e)

    async def save_artifact(name: str, content: str, media_type: str = "text/markdown") -> dict:
        """Save a document for the user to download later (design or review notes, user
        stories, reports). Text only: text/markdown (default, name ends in .md), text/plain
        (.txt), text/csv (.csv) or application/json (.json); up to 1 MiB. Kept for a limited
        time (see expires_at). Give the user the download_path as a link. A revision is a new
        artifact: save it again, then delete the old one if the user wants."""
        ident, pool = await _begin()
        oid = ident.principal.oid
        try:
            data = validate(name, content, media_type)
        except ArtifactInputError as e:
            audit_artifact(ident, "artifact_change", "create", None, "rejected", reason=str(e))
            raise ToolError(str(e)) from None
        artifact_id = str(uuid.uuid4())
        async with pool.connection() as conn, owner_scoped(conn, oid):
            expired = await db.delete_expired(conn)
            if await db.count_live(conn) >= MAX_LIVE_PER_USER:
                audit_artifact(ident, "artifact_change", "create", None, "limit")
                raise ToolError(
                    f"you have {MAX_LIVE_PER_USER} saved artifacts (the limit): "
                    "delete some with delete_artifact first"
                )
            row = await db.insert(
                conn,
                artifact_id=artifact_id,
                owner_oid=oid,
                name=name,
                media_type=media_type,
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                agent_session_id=current_correlation().get("agent_session_id"),
                retention_days=artifacts.retention_days,
            )
            try:  # inside the transaction: a failed upload leaves no row
                await asyncio.to_thread(
                    artifacts.store.put, object_key(oid, artifact_id), data, media_type
                )
            except ArtifactStoreError as e:
                log.error("artifact not stored: %s", e)
                audit_artifact(ident, "artifact_change", "create", artifact_id, "error")
                raise ToolError("the artifact could not be saved; try again later") from None
        await _drop_objects(oid, expired)
        audit_artifact(
            ident,
            "artifact_change",
            "create",
            artifact_id,
            "ok",
            media_type=media_type,
            size_bytes=len(data),
        )
        return _public(row)

    async def list_artifacts() -> dict:
        """List the documents you saved with save_artifact (newest first) that have not expired."""
        ident, pool = await _begin()
        async with pool.connection() as conn, owner_scoped(conn, ident.principal.oid):
            expired = await db.delete_expired(conn)
            rows = await db.list_live(conn)
        await _drop_objects(ident.principal.oid, expired)
        return {
            "artifacts": [_public(r) for r in rows],
            "limit": MAX_LIVE_PER_USER,
            "retention_days": artifacts.retention_days,
        }

    async def read_artifact(artifact_id: str) -> dict:
        """Return one of your saved documents with its text, e.g. to revise it."""
        ident, pool = await _begin()
        oid = ident.principal.oid
        async with pool.connection() as conn, owner_scoped(conn, oid):
            row = await db.get_live(conn, artifact_id)
        if row is None:
            audit_artifact(ident, "artifact_access", "read", db.parse_id(artifact_id), "not_found")
            raise ToolError(NOT_FOUND)
        try:
            data = await asyncio.to_thread(artifacts.store.get, object_key(oid, row.id))
        except ArtifactStoreError as e:
            log.error("artifact not readable: %s", e)
            audit_artifact(ident, "artifact_access", "read", row.id, "error")
            raise ToolError("the artifact could not be read; try again later") from None
        if data is None:  # content gone (store lifecycle) before the row expired
            audit_artifact(ident, "artifact_access", "read", row.id, "content_missing")
            raise ToolError(NOT_FOUND)
        audit_artifact(ident, "artifact_access", "read", row.id, "ok")
        return {**_public(row), "content": data.decode("utf-8")}

    async def delete_artifact(artifact_id: str) -> dict:
        """Delete one of your saved documents."""
        ident, pool = await _begin()
        oid = ident.principal.oid
        async with pool.connection() as conn, owner_scoped(conn, oid):
            deleted = await db.delete(conn, artifact_id)
        key = db.parse_id(artifact_id)
        if not deleted:
            audit_artifact(ident, "artifact_change", "delete", key, "not_found")
            raise ToolError(NOT_FOUND)
        await _drop_objects(oid, [key])
        audit_artifact(ident, "artifact_change", "delete", key, "ok")
        return {"id": key, "deleted": True}

    return [save_artifact, list_artifacts, read_artifact, delete_artifact]
