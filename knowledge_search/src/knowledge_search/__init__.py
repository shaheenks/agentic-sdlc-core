"""Knowledge search over the JSONL knowledge store, filtered by the caller's data scope (Knowledge Search;
FR-KNOW-002, FR-AUTHZ-004, NFR-ARCH-004, DEC-0011).

Only declared callers (the MCP servers' service accounts, proven by a Google ID token minted for this
service) may query, and every query carries a filter attribute: the source IDs the MCP server computed for its
user. A query without one is refused. The store is read once at start-up from `KNOWLEDGE_PATH`."""

import logging
import os
from dataclasses import dataclass

from sdlc_identity import GoogleTokens, Rejected
from sdlc_knowledge import QUERY, Embedder, StoreError, embedder_from_env, read_store
from sdlc_service import health_routes
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from knowledge_search.index import HYBRID, KEYWORD, MODES, Index

SERVICE = "knowledge_search"
DEFAULT_PORT = 8083
LOCAL_ENV = "local"
MAX_QUERY = 2000
log = logging.getLogger(SERVICE)


@dataclass(frozen=True)
class Settings:
    env: str
    knowledge_path: str
    public_url: str
    allowed_callers: frozenset[str]
    caller_auth: str  # id_token, or none (local only)

    @classmethod
    def from_env(cls, environ=None) -> "Settings":
        e = os.environ if environ is None else environ
        settings = cls(
            env=e.get("SDLC_ENV", LOCAL_ENV),
            knowledge_path=e.get("KNOWLEDGE_PATH", "/app/knowledge"),
            public_url=e.get("PUBLIC_URL", f"http://localhost:{e.get('PORT', DEFAULT_PORT)}").rstrip("/"),
            allowed_callers=frozenset(a.strip().lower() for a in e.get("ALLOWED_CALLERS", "").split(",") if a.strip()),
            caller_auth=e.get("CALLER_AUTH", "id_token"),
        )
        if settings.caller_auth not in ("id_token", "none"):
            raise SystemExit("CALLER_AUTH must be id_token or none")
        if settings.caller_auth == "none" and settings.env != LOCAL_ENV:
            raise SystemExit("CALLER_AUTH=none is allowed only in the local environment (fail closed)")
        if settings.caller_auth == "id_token" and not settings.allowed_callers:
            raise SystemExit("ALLOWED_CALLERS must name the MCP servers' service accounts (fail closed)")
        return settings


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status)


def _sources(body) -> list[str] | None:
    """The filter attribute: {"filter": {"sources": [...]}}; None when it is missing or malformed."""
    f = body.get("filter") if isinstance(body, dict) else None
    sources = f.get("sources") if isinstance(f, dict) else None
    if not isinstance(sources, list) or not all(isinstance(s, str) for s in sources):
        return None
    return sources


def _int(value, default: int, low: int, high: int) -> int | None:
    if value is None:
        return default
    return value if isinstance(value, int) and not isinstance(value, bool) and low <= value <= high else None


def create_app(
    settings: Settings | None = None,
    index: Index | None = None,
    embedder: Embedder | None = None,
    tokens: GoogleTokens | None = None,
) -> Starlette:
    """With no `index`, only the health route is served (the store is loaded by `main`)."""
    if index is None:
        return Starlette(routes=health_routes(SERVICE))
    assert settings is not None and embedder is not None
    tokens = tokens or GoogleTokens()
    audiences = {settings.public_url}

    async def caller(request: Request) -> str | JSONResponse:
        if settings.caller_auth == "none":
            return "local"
        header = request.headers.get("authorization") or ""
        token = header[7:].strip() if header[:7].lower() == "bearer " else ""
        try:
            claims = await tokens.claims(token)
        except Rejected as exc:
            return _error(401, "unauthenticated", exc.reason)
        account = (claims.get("email") if claims.get("email_verified") else "") or ""
        if claims.get("kind") != "id" or claims.get("client_id") not in audiences:
            return _error(401, "unauthenticated", "wrong_audience")
        if account.lower() not in settings.allowed_callers:
            return _error(403, "forbidden", "undeclared_caller")
        return account.lower()

    async def body_of(request: Request):
        try:
            return await request.json()
        except ValueError:
            return None

    async def search(request: Request) -> JSONResponse:
        who = await caller(request)
        if isinstance(who, JSONResponse):
            return who
        body = await body_of(request)
        sources = _sources(body)
        if sources is None:
            return _error(400, "filter_required", "every query needs filter.sources, the readable source IDs")
        query = body.get("query")
        mode = body.get("mode") or HYBRID
        limit = _int(body.get("limit"), 10, 1, 50)
        if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY:
            return _error(400, "invalid_argument", f"query must be 1 to {MAX_QUERY} characters")
        if mode not in MODES or limit is None:
            return _error(400, "invalid_argument", f"mode is one of {', '.join(MODES)}; limit is 1 to 50")
        vector = None
        if mode != KEYWORD:
            if embedder.model != index.embedding_model:
                return _error(409, "embedding_model_mismatch", "the store was embedded with another model")
            vector = (await embedder.embed([query], QUERY))[0]
        hits = index.search(mode, sources, limit, query, vector)
        log.info("search", extra={"caller": who, "mode": mode, "sources": len(sources), "results": len(hits)})
        return JSONResponse(
            {
                "results": [
                    {
                        "id": h.chunk.id,
                        "source_id": h.chunk.source_id,
                        "classification": h.chunk.classification,
                        "path": h.chunk.path,
                        "link": h.chunk.link,
                        "lines": [h.chunk.start_line, h.chunk.end_line],
                        "heading": h.chunk.heading,
                        "text": h.chunk.text,
                        "score": round(h.score, 6),
                    }
                    for h in hits
                ]
            }
        )

    async def graph(request: Request) -> JSONResponse:
        who = await caller(request)
        if isinstance(who, JSONResponse):
            return who
        body = await body_of(request)
        sources = _sources(body)
        if sources is None:
            return _error(400, "filter_required", "every query needs filter.sources, the readable source IDs")
        entity, name = body.get("entity") or "", body.get("name") or ""
        depth, limit = _int(body.get("depth"), 1, 1, 2), _int(body.get("limit"), 50, 1, 200)
        if not isinstance(entity, str) or not isinstance(name, str) or not (entity or name.strip()):
            return _error(400, "invalid_argument", "give an entity ID or a name")
        if depth is None or limit is None or len(name) > 200 or len(entity) > 500:
            return _error(400, "invalid_argument", "depth is 1 or 2; limit is 1 to 200")
        result = index.graph(sources, entity=entity, name=name, depth=depth, limit=limit)
        log.info("graph", extra={"caller": who, "sources": len(sources), "nodes": len(result["nodes"])})
        return JSONResponse(result)

    async def status(request: Request) -> JSONResponse:
        """The ingest run behind this image (FR-KNOW-003), for the readable sources only."""
        who = await caller(request)
        if isinstance(who, JSONResponse):
            return who
        sources = set(_sources(await body_of(request)) or ())
        m = index.manifest
        return JSONResponse(
            {
                "finished_at": m.get("finished_at"),
                "config_version": m.get("config_version"),
                "embedding": m.get("embedding"),
                "sources": {s: v for s, v in (m.get("sources") or {}).items() if s in sources},
            }
        )

    return Starlette(
        routes=[
            *health_routes(SERVICE),
            Route("/search", search, methods=["POST"]),
            Route("/graph", graph, methods=["POST"]),
            Route("/status", status, methods=["POST"]),
        ]
    )


def load(settings: Settings) -> Index:
    try:
        return Index(read_store(settings.knowledge_path))
    except StoreError as exc:
        raise SystemExit(f"knowledge store at {settings.knowledge_path} is unusable: {exc}") from exc


def create_service() -> Starlette:
    settings = Settings.from_env()
    return create_app(settings, load(settings), embedder_from_env())
