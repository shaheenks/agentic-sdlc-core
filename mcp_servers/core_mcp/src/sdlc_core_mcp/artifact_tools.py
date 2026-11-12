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
import re
import uuid
from dataclasses import dataclass

from fastmcp.exceptions import ToolError
from psycopg.errors import UniqueViolation
from sdlc_artifacts import (
    MAX_LIVE_PER_USER,
    MAX_VERSIONS_PER_DOCUMENT,
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


def split_lines(text: str) -> list[str]:
    """Lines as the chat's document viewer numbers them (ui/copilotkit ArtifactViewer): CRLF
    counts as one break, and a trailing newline gives a last, empty line."""
    return text.replace("\r\n", "\n").split("\n")


def number_lines(text: str) -> str:
    return "\n".join(f"{n}\t{line}" for n, line in enumerate(split_lines(text), start=1))


_NUMBERED = re.compile(r"^\d+\t")


def looks_numbered(content: str) -> bool:
    """True when the content is read_artifact(numbered=true) output saved back unchanged: every
    line starts with its own number and a tab (1, 2, 3, ...). Ordinary TSV does not count."""
    lines = split_lines(content)
    if len(lines) < 2:
        return False
    return all(
        _NUMBERED.match(line) and line.startswith(f"{n}\t") for n, line in enumerate(lines, 1)
    )


def public_row(row: db.ArtifactRow) -> dict:
    """Public view: `id` is the document's stable id; the link opens its latest version."""
    return {**row.public(), "download_path": f"{DOWNLOAD_PATH}{row.document_id}"}


def make_artifact_tools(artifacts: Artifacts) -> list:
    async def _begin() -> tuple[Identity, object]:
        ident = await request_identity()
        if not artifacts.enabled:
            raise ToolError("artifacts are not configured on this server")
        return ident, await artifacts.knowledge.open_pool()

    async def _drop_objects(oid: str, row_ids: list[str]) -> None:
        for row_id in row_ids:  # best effort: the store's lifecycle removes leftovers
            try:
                await asyncio.to_thread(artifacts.store.delete, object_key(oid, row_id))
            except ArtifactStoreError as e:
                log.warning("artifact content not deleted (%s): %s", row_id, e)

    async def save_artifact(
        name: str,
        content: str,
        media_type: str = "text/markdown",
        replaces: str | None = None,
        base_version: int | None = None,
    ) -> dict:
        """Save a document for the user to download later (design or review notes, user
        stories, reports). Text only: text/markdown (default, name ends in .md), text/plain
        (.txt), text/csv (.csv) or application/json (.json); up to 1 MiB. Kept for a limited
        time (see expires_at). Give the user the download_path as a link.
        To revise one of the user's documents, pass its id as `replaces` and the version you
        read and revised as `base_version`: this saves the next version of the same document
        (same id and link; older versions stay readable). If a newer version exists, nothing
        is saved and the answer names the latest version."""
        ident, pool = await _begin()
        oid = ident.principal.oid
        action = "update" if replaces else "create"
        try:
            if replaces and base_version is None:
                raise ArtifactInputError(
                    "pass base_version: the version you read with read_artifact and revised"
                )
            if replaces and looks_numbered(content):
                raise ArtifactInputError(
                    "the content still has line numbers from read_artifact(numbered=true): "
                    "remove the '<n><tab>' prefix from every line"
                )
            data = validate(name, content, media_type)
        except ArtifactInputError as e:
            audit_artifact(ident, "artifact_change", action, None, "rejected", reason=str(e))
            raise ToolError(str(e)) from None
        row_id = str(uuid.uuid4())
        document_id = db.parse_id(replaces) if replaces else row_id
        async with pool.connection() as conn, owner_scoped(conn, oid):
            expired = await db.delete_expired(conn)
            version = 1
            if replaces:
                latest = await db.latest_version(conn, replaces)
                if latest is None:  # missing, expired or not the caller's: the same answer
                    audit_artifact(ident, "artifact_change", action, document_id, "not_found")
                    raise ToolError(NOT_FOUND)
                if base_version != latest:  # revising an older version would drop newer edits
                    audit_artifact(
                        ident,
                        "artifact_change",
                        action,
                        document_id,
                        "stale",
                        base_version=base_version,
                        latest_version=latest,
                    )
                    raise ToolError(
                        f"not saved: you revised version {base_version}, but the latest version "
                        f"is {latest}. Tell the user and ask how to proceed; do not overwrite it"
                    )
                version = latest + 1
                # a new version adds no document, so only the version limit applies (CH-0004)
                if await db.count_versions(conn, replaces) >= MAX_VERSIONS_PER_DOCUMENT:
                    audit_artifact(
                        ident, "artifact_change", action, document_id, "limit", limit="versions"
                    )
                    raise ToolError(
                        f"this document already has {MAX_VERSIONS_PER_DOCUMENT} versions (the "
                        "limit): save the text as a new document, or delete this one with "
                        "delete_artifact first"
                    )
            elif await db.count_live(conn) >= MAX_LIVE_PER_USER:
                audit_artifact(
                    ident, "artifact_change", action, document_id, "limit", limit="documents"
                )
                raise ToolError(
                    f"you have {MAX_LIVE_PER_USER} saved documents (the limit): delete some with "
                    "delete_artifact first"
                )
            try:
                row = await db.insert(
                    conn,
                    artifact_id=row_id,
                    document_id=document_id,
                    version=version,
                    owner_oid=oid,
                    name=name,
                    media_type=media_type,
                    size_bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                    agent_session_id=current_correlation().get("agent_session_id"),
                    retention_days=artifacts.retention_days,
                )
            except UniqueViolation:  # two revisions of one document at the same moment
                audit_artifact(ident, "artifact_change", action, document_id, "conflict")
                raise ToolError("the document changed at the same time; try again") from None
            try:  # inside the transaction: a failed upload leaves no row
                await asyncio.to_thread(
                    artifacts.store.put, object_key(oid, row_id), data, media_type
                )
            except ArtifactStoreError as e:
                log.error("artifact not stored: %s", e)
                audit_artifact(ident, "artifact_change", action, document_id, "error")
                raise ToolError("the artifact could not be saved; try again later") from None
        await _drop_objects(oid, expired)
        audit_artifact(
            ident,
            "artifact_change",
            action,
            document_id,
            "ok",
            version=version,
            media_type=media_type,
            size_bytes=len(data),
        )
        return public_row(row)

    async def list_artifacts() -> dict:
        """List the documents you saved with save_artifact (latest version of each, newest
        first) that have not expired."""
        ident, pool = await _begin()
        async with pool.connection() as conn, owner_scoped(conn, ident.principal.oid):
            expired = await db.delete_expired(conn)
            rows = await db.list_live(conn)
        await _drop_objects(ident.principal.oid, expired)
        return {
            "artifacts": [public_row(r) for r in rows],
            "limit": MAX_LIVE_PER_USER,  # documents
            "versions_per_document": MAX_VERSIONS_PER_DOCUMENT,
            "retention_days": artifacts.retention_days,
        }

    async def read_artifact(
        artifact_id: str, version: int | None = None, numbered: bool = False
    ) -> dict:
        """Return one of your saved documents with its text, e.g. to revise it. The latest
        version unless `version` is given. `numbered=true` prefixes every line with its number
        and a tab ("12<tab>text"), the numbering of the user's document viewer: use it when the
        user's comments refer to line numbers, and never save those prefixes."""
        ident, pool = await _begin()
        oid = ident.principal.oid
        key = db.parse_id(artifact_id)
        async with pool.connection() as conn, owner_scoped(conn, oid):
            row = await db.get_live(conn, artifact_id, version)
        if row is None:
            audit_artifact(ident, "artifact_access", "read", key, "not_found")
            raise ToolError(NOT_FOUND)
        try:
            data = await asyncio.to_thread(artifacts.store.get, object_key(oid, row.row_id))
        except ArtifactStoreError as e:
            log.error("artifact not readable: %s", e)
            audit_artifact(ident, "artifact_access", "read", key, "error", version=row.version)
            raise ToolError("the artifact could not be read; try again later") from None
        if data is None:  # content gone (store lifecycle) before the row expired
            audit_artifact(
                ident, "artifact_access", "read", key, "content_missing", version=row.version
            )
            raise ToolError(NOT_FOUND)
        audit_artifact(ident, "artifact_access", "read", key, "ok", version=row.version)
        text = data.decode("utf-8")
        if numbered:
            return {**public_row(row), "content": number_lines(text), "numbered": True}
        return {**public_row(row), "content": text}

    async def delete_artifact(artifact_id: str) -> dict:
        """Delete one of your saved documents, with all its versions."""
        ident, pool = await _begin()
        oid = ident.principal.oid
        key = db.parse_id(artifact_id)
        async with pool.connection() as conn, owner_scoped(conn, oid):
            row_ids = await db.delete_document(conn, artifact_id)
        if not row_ids:
            audit_artifact(ident, "artifact_change", "delete", key, "not_found")
            raise ToolError(NOT_FOUND)
        await _drop_objects(oid, row_ids)
        audit_artifact(ident, "artifact_change", "delete", key, "ok", versions=len(row_ids))
        return {"id": key, "deleted": True, "versions": len(row_ids)}

    return [save_artifact, list_artifacts, read_artifact, delete_artifact]
