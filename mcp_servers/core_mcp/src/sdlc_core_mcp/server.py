"""Core MCP server (core_mcp).

Stage 1: ping, list_skills, load_skill over streamable HTTP.
Stage 2: every MCP request needs a valid Entra ID user token (401 otherwise); whoami;
         config via ConfigStore (fail closed); JSON audit log for every tool call.
Stage 3: RBAC from config: tools/list shows only permitted tools, every tools/call is
         authorized (tool + argument limits) and audited with the matched rule; stub SDLC
         tools; admin tools config_info / config_explain; whoami(explain).
Stage 4: skills come from the config snapshot (skills.yaml + team add-ons) and are filtered
         per user; get_agent_context returns the caller's team instructions and context.
Stage 5-6: search_knowledge and graph_query over the RLS-protected knowledge store (sdlc_app role).
"""

import inspect
import logging
import os
from collections.abc import Callable

import uvicorn
from fastmcp import FastMCP
from fastmcp.server.auth import AuthProvider, RemoteAuthProvider
from sdlc_auth import GraphGroupResolver, GroupResolver
from sdlc_auth.entra import EntraTokenVerifier
from sdlc_config import ConfigStore, PolicyCache, Snapshot, skill_decision
from starlette.middleware import Middleware as ASGIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from sdlc_core_mcp.admin_tools import make_admin_tools
from sdlc_core_mcp.artifact_tools import Artifacts, make_artifact_tools
from sdlc_core_mcp.artifacts_api import add_artifact_routes
from sdlc_core_mcp.audit import (
    HiddenSkillError,
    PolicyMiddleware,
    audit_skill_access,
    audit_skills_list,
)
from sdlc_core_mcp.auth_audit import AuthFailureAuditMiddleware
from sdlc_core_mcp.connected_tools import Connected, connection_problems, make_connected_tools
from sdlc_core_mcp.connections_api import add_connection_routes
from sdlc_core_mcp.identity import request_identity
from sdlc_core_mcp.knowledge_tools import Knowledge, make_knowledge_tools
from sdlc_core_mcp.team_tools import make_team_tools
from sdlc_core_mcp.telemetry import setup_tracing

log = logging.getLogger("sdlc.mcp")


def catalog_problems(snapshot: Snapshot, registered: dict[str, frozenset[str]]) -> list[str]:
    """Constrained arguments (tools.yaml `args`) must exist on the registered tool."""
    problems = []
    for name, params in registered.items():
        tool = snapshot.tools.get(name)
        if tool is None:
            continue  # not in the catalog: never exposed (warned separately)
        missing = tool.args - params
        if missing:
            problems.append(
                f"tools.yaml: {name}: args {sorted(missing)} are not parameters of the tool"
            )
    return problems


def build_server(
    store: ConfigStore,
    auth: AuthProvider,
    group_resolver: GroupResolver | None = None,
    knowledge: Knowledge | None = None,
    connected: Connected | None = None,
    artifacts: Artifacts | None = None,
) -> FastMCP:
    cache = PolicyCache()
    mcp = FastMCP(
        name="sdlc-core-mcp",
        instructions="Central SDLC tool server. Use list_skills, then load_skill before a task.",
        auth=auth,
        middleware=[PolicyMiddleware(store, group_resolver, cache)],
    )
    registered: dict[str, frozenset[str]] = {}

    def register(fn: Callable) -> None:
        registered[fn.__name__] = frozenset(inspect.signature(fn).parameters)
        mcp.tool(fn)

    def ping() -> str:
        """Liveness check. Returns 'pong'."""
        return "pong"

    async def whoami(explain: bool = False) -> dict:
        """Who the server thinks you are. explain=true adds your teams, roles and tools, each
        with the config rule that grants it."""
        ident = await request_identity()
        p = ident.principal
        result = {
            "oid": p.oid,
            "upn": p.upn,
            "name": p.name,
            "tenant_id": p.tid,
            "groups": list(ident.group_aliases),
            "user": ident.user_alias,
            "app_roles": sorted(p.app_roles),
            "unmapped_group_count": ident.unmapped_group_count,
            "non_guid_group_claims": p.non_guid_group_claims,
            "group_source": ident.group_source,
            "config_version": ident.snapshot.version,
        }
        if explain:
            result["policy"] = ident.policy.explain()
        return result

    async def list_skills() -> list[dict]:
        """List the SDLC skills available to you: name, description, tags (e.g. goldfish-lens,
        brief-questions, doc-template) and, for a team add-on, its team. Load one with
        load_skill."""
        ident = await request_identity()
        skills = ident.snapshot.skills
        visible = sorted(ident.policy.skills)
        audit_skills_list(ident, visible, len(skills) - len(visible))
        listed = []
        for name in visible:
            skill = skills[name]
            item = {"name": name, "description": skill.description, "tags": sorted(skill.tags)}
            if skill.team is not None:
                item["team"] = skill.team
            listed.append(item)
        return listed

    async def load_skill(name: str) -> dict[str, str]:
        """Return the full instructions of a skill returned by list_skills."""
        ident = await request_identity()
        decision = skill_decision(ident.snapshot, ident.policy, name)
        audit_skill_access(ident, name, decision)  # the audit records the real reason
        # Hidden and non-existent skills get the same answer: existence is not disclosed.
        if not decision.allowed:
            raise HiddenSkillError(name, decision.matched_rule, decision.reason)
        skill = ident.snapshot.skills[name]
        return {
            "name": skill.name,
            "description": skill.description,
            "instructions": skill.instructions,
        }

    core = [ping, whoami, list_skills, load_skill, *make_team_tools()]
    knowledge_tools = make_knowledge_tools(knowledge) if knowledge else []
    connected = connected or Connected(service=None)  # tools answer "not configured"
    connected_tools = make_connected_tools(connected)
    artifacts = artifacts or Artifacts(store=None, knowledge=None)  # tools answer "not configured"
    for fn in [
        *core,
        *make_admin_tools(store, cache),
        *knowledge_tools,
        *connected_tools,
        *make_artifact_tools(artifacts),
    ]:
        register(fn)
    verifier = getattr(auth, "token_verifier", None)
    if verifier is not None:  # the Connections and Artifacts APIs use the same token checks as MCP
        add_connection_routes(mcp, connected, verifier)
        add_artifact_routes(mcp, artifacts, verifier, store, group_resolver, cache)

    # Catalog vs code: fail startup on bad constraint args; re-check (log) on every reload.
    problems = catalog_problems(store.current(), registered)
    problems += connection_problems(store.current(), set(registered))
    if problems:
        raise ValueError("config does not match the registered tools: " + "; ".join(problems))
    uncatalogued = sorted(set(registered) - set(store.current().tools))
    if uncatalogued:
        log.warning("tools not in tools.yaml are never exposed: %s", uncatalogued)

    def recheck(snapshot: Snapshot) -> None:
        problems = catalog_problems(snapshot, registered)
        for problem in problems + connection_problems(snapshot, set(registered)):
            log.error("config %s: %s", snapshot.version, problem)

    store.subscribe(recheck)

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "skills": len(store.current().skills),
                "config_version": store.current().version,
                "config_reload_error": store.last_error is not None,
            }
        )

    return mcp


def build_http_app(server: FastMCP, store: ConfigStore):
    """HTTP app with rejected-token auditing (auth_failure events) around the MCP endpoint."""
    return server.http_app(middleware=[ASGIMiddleware(AuthFailureAuditMiddleware, store=store)])


def build_auth(
    snapshot: Snapshot, public_url: str, store: ConfigStore | None = None
) -> RemoteAuthProvider:
    """Entra token verification + OAuth protected-resource metadata (RFC 9728).

    The 401 WWW-Authenticate header points MCP clients (e.g. Antigravity) at
    /.well-known/oauth-protected-resource, which names Entra as the authorization server.
    Identity settings are read once at startup; changing them needs a restart. The block list
    (E3) is read from the store's current snapshot on every request, so it applies on reload.
    """
    platform = snapshot.platform
    verifier = EntraTokenVerifier(
        tenant_id=platform.tenant_id,
        audience=list(platform.audience),
        required_scopes=list(platform.required_scopes),
        issuer=platform.issuer,
        jwks_uri=platform.jwks_uri,
        blocked_reason=(lambda oid: store.current().blocked.get(oid)) if store else None,
    )
    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=[platform.issuer],
        base_url=public_url,
        resource_name="sdlc-mcp",
    )


def build_group_resolver(snapshot: Snapshot) -> GroupResolver | None:
    platform = snapshot.platform
    if platform.groups_overage_fallback != "graph_transitive_member_of":
        return None
    secret = os.environ.get("ENTRA_GRAPH_CLIENT_SECRET")
    if not secret:
        log.warning(
            "groups overage fallback disabled: ENTRA_GRAPH_CLIENT_SECRET not set "
            "(users with too many groups will get no groups)"
        )
        return None
    return GraphGroupResolver(
        tenant_id=platform.tenant_id,
        client_id=os.environ["ENTRA_API_CLIENT_ID"],
        client_secret=secret,
        ttl_seconds=platform.groups_cache_ttl_seconds,
        graph_host=platform.graph_host,
        authority_host=platform.authority_host,
    )


def build_knowledge(snapshot: Snapshot) -> Knowledge:
    """Read-only pool as sdlc_app (RLS) + query embedder (platform.yaml knowledge.embedding)."""
    from psycopg_pool import AsyncConnectionPool
    from sdlc_db import GeminiEmbedder, conninfo

    pool = AsyncConnectionPool(conninfo("app"), min_size=1, max_size=10, open=False)
    platform = snapshot.platform
    return Knowledge(pool, GeminiEmbedder(platform.embedding_model, platform.embedding_dimensions))


def build_connected(store: ConfigStore, knowledge: Knowledge | None) -> Connected:
    """User connections (version-01 M6): off unless SDLC_USER_SECRETS_BACKEND is set. Writes per
    user are serialised by a process lock plus a Postgres advisory lock (several instances)."""
    from contextlib import asynccontextmanager

    from sdlc_connectors.service import ConnectionService, process_locks
    from sdlc_connectors.user_store import store_from_env

    user_store = store_from_env()
    page = os.environ.get("SDLC_CONNECTIONS_PAGE", "/chat/connections")
    if user_store is None:
        log.info("user connections off (SDLC_USER_SECRETS_BACKEND not set)")
        return Connected(service=None, page_url=page)
    local = process_locks()

    @asynccontextmanager
    async def lock(key: str):
        async with local(key):
            if knowledge is None:
                yield
                return
            pool = await knowledge.open_pool()
            async with pool.connection() as conn, conn.transaction():
                # advisory locks need no table privileges: fine for the read-only sdlc_app role
                await conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"user-connections:{key}",),
                )
                yield

    log.info("user connections on (%s store)", user_store.name)
    return Connected(ConnectionService(user_store, store.current, lock), page_url=page)


def build_artifacts(knowledge: Knowledge | None) -> Artifacts:
    """Artifacts (version-03 P5): off unless SDLC_ARTIFACT_STORE is set (file:// or gs://).
    Retention should match the GCS bucket lifecycle (artifact_retention_days)."""
    from sdlc_artifacts import store_from_env

    store = store_from_env()
    days = float(os.environ.get("SDLC_ARTIFACT_RETENTION_DAYS", "7"))
    if store is None:
        log.info("artifacts off (SDLC_ARTIFACT_STORE not set)")
    else:
        log.info("artifacts on (%s store, %s days)", store.name, days)
    return Artifacts(store, knowledge, days)


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(message)s")
    setup_tracing()  # no-op unless OTEL_EXPORTER_OTLP_(TRACES_)ENDPOINT is set
    store = ConfigStore.from_env()  # raises ConfigError on invalid config: fail closed
    store.start_updates()  # folder: watch files; bundles (GCP): poll the `current` pointer
    snapshot = store.current()
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8080"))
    knowledge = build_knowledge(snapshot)
    server = build_server(
        store,
        build_auth(snapshot, os.environ.get("MCP_PUBLIC_URL", f"http://127.0.0.1:{port}"), store),
        build_group_resolver(snapshot),
        knowledge,
        build_connected(store, knowledge),
        build_artifacts(knowledge),
    )
    uvicorn.run(build_http_app(server, store), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
