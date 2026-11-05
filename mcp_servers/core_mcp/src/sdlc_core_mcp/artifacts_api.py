"""Artifacts download API (version-03 P5, F2): the browser lists, downloads and deletes the
caller's own artifacts.

  GET    /artifacts/        the caller's artifacts (metadata only)
  GET    /artifacts/{id}    download (attachment, never rendered on our origin)
  DELETE /artifacts/{id}    needs `X-SDLC-Request: 1` (a cross-site form or image cannot send it)

Served by the MCP server and reached by the browser through oauth2-proxy at /artifacts/ (the proxy
adds the user's Entra token as X-Forwarded-Access-Token; `Authorization: Bearer` works too). The
token goes through the same verifier as MCP requests (issuer, audience, scope, tenant, block list),
then the caller's policy must allow the matching tool (`list_artifacts`, `read_artifact`,
`delete_artifact`): no tool, no API. Ownership is enforced by RLS as in the tools; another user's
id answers 404 like a missing one. Audit as the tools: `artifact_access` / `artifact_change`.
"""

import asyncio
import logging

from fastmcp import FastMCP
from fastmcp.server.auth import TokenVerifier
from sdlc_artifacts import ArtifactStoreError, object_key
from sdlc_auth import GroupResolver, principal_from_claims
from sdlc_config import ConfigStore, PolicyCache
from sdlc_db import artifacts as db
from sdlc_db import owner_scoped
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from sdlc_core_mcp.artifact_tools import Artifacts, public_row
from sdlc_core_mcp.audit import audit_artifact, new_request_id
from sdlc_core_mcp.connections_api import access_token_from
from sdlc_core_mcp.identity import Identity, resolve_identity

log = logging.getLogger("sdlc.mcp")
WRITE_HEADER = "x-sdlc-request"
# Downloads are data, not pages: never sniffed, framed, scripted or cached by shared caches.
DOWNLOAD_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
    "Cache-Control": "private, no-store",
}


def add_artifact_routes(
    mcp: FastMCP,
    artifacts: Artifacts,
    verifier: TokenVerifier,
    store: ConfigStore,
    group_resolver: GroupResolver | None,
    cache: PolicyCache,
) -> None:
    async def caller(request: Request, tool: str) -> Identity | Response:
        token = access_token_from(request)
        access = await verifier.load_access_token(token) if token else None
        if access is None:
            return JSONResponse({"detail": "sign-in required"}, status_code=401)
        try:
            principal = principal_from_claims(access.claims)
        except ValueError:
            return JSONResponse({"detail": "not a user token"}, status_code=401)
        ident = await resolve_identity(
            principal, store.current(), group_resolver, cache, new_request_id()
        )
        if not ident.policy.allows(tool):
            return JSONResponse({"detail": "artifacts are not available to you"}, status_code=403)
        if not artifacts.enabled:
            return JSONResponse(
                {"detail": "artifacts are not configured on this server"}, status_code=503
            )
        return ident

    def not_found() -> JSONResponse:
        return JSONResponse({"detail": "artifact not found"}, status_code=404)

    @mcp.custom_route("/artifacts/", methods=["GET"])
    async def list_artifacts(request: Request) -> Response:
        ident = await caller(request, "list_artifacts")
        if isinstance(ident, Response):
            return ident
        pool = await artifacts.knowledge.open_pool()
        async with pool.connection() as conn, owner_scoped(conn, ident.principal.oid):
            rows = await db.list_live(conn)
        return JSONResponse(
            {"artifacts": [public_row(r) for r in rows], "retention_days": artifacts.retention_days}
        )

    @mcp.custom_route("/artifacts/{artifact_id}", methods=["GET", "DELETE"])
    async def one_artifact(request: Request) -> Response:
        artifact_id = request.path_params["artifact_id"]
        key = db.parse_id(artifact_id)
        if request.method == "DELETE":
            ident = await caller(request, "delete_artifact")
            if isinstance(ident, Response):
                return ident
            if request.headers.get(WRITE_HEADER) != "1":
                return JSONResponse({"detail": f"missing {WRITE_HEADER} header"}, status_code=403)
            oid = ident.principal.oid
            pool = await artifacts.knowledge.open_pool()
            async with pool.connection() as conn, owner_scoped(conn, oid):
                deleted = await db.delete(conn, artifact_id)
            if not deleted:
                audit_artifact(ident, "artifact_change", "delete", key, "not_found", via="api")
                return not_found()
            try:
                await asyncio.to_thread(artifacts.store.delete, object_key(oid, key))
            except ArtifactStoreError as e:  # the row is gone; the bucket lifecycle cleans up
                log.warning("artifact content not deleted (%s): %s", key, e)
            audit_artifact(ident, "artifact_change", "delete", key, "ok", via="api")
            return JSONResponse({"id": key, "deleted": True})

        ident = await caller(request, "read_artifact")
        if isinstance(ident, Response):
            return ident
        oid = ident.principal.oid
        pool = await artifacts.knowledge.open_pool()
        async with pool.connection() as conn, owner_scoped(conn, oid):
            row = await db.get_live(conn, artifact_id)
        if row is None:
            audit_artifact(ident, "artifact_access", "download", key, "not_found")
            return not_found()
        try:
            data = await asyncio.to_thread(artifacts.store.get, object_key(oid, row.id))
        except ArtifactStoreError as e:
            log.error("artifact not readable: %s", e)
            audit_artifact(ident, "artifact_access", "download", row.id, "error")
            return JSONResponse({"detail": "the artifact could not be read"}, status_code=502)
        if data is None:
            audit_artifact(ident, "artifact_access", "download", row.id, "content_missing")
            return not_found()
        audit_artifact(ident, "artifact_access", "download", row.id, "ok")
        # row.name passed sdlc_artifacts.limits (letters, digits, . _ - space): safe in the header
        return Response(
            data,
            media_type=f"{row.media_type}; charset=utf-8",
            headers={
                **DOWNLOAD_HEADERS,
                "Content-Disposition": f'attachment; filename="{row.name}"',
            },
        )
