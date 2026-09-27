"""Bootstrap MCP server.

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
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AuthProvider, RemoteAuthProvider
from sdlc_auth import GraphGroupResolver, GroupResolver
from sdlc_auth.entra import EntraTokenVerifier
from sdlc_config import ConfigStore, PolicyCache, Snapshot, skill_decision
from starlette.middleware import Middleware as ASGIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from sdlc_mcp_bootstrap.admin_tools import make_admin_tools
from sdlc_mcp_bootstrap.audit import PolicyMiddleware, audit_skill_access, audit_skills_list
from sdlc_mcp_bootstrap.auth_audit import AuthFailureAuditMiddleware
from sdlc_mcp_bootstrap.identity import request_identity
from sdlc_mcp_bootstrap.knowledge_tools import Knowledge, make_knowledge_tools
from sdlc_mcp_bootstrap.sdlc_tools import SDLC_TOOLS

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
) -> FastMCP:
    cache = PolicyCache()
    mcp = FastMCP(
        name="sdlc-mcp-bootstrap",
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
            "app_roles": sorted(p.app_roles),
            "unmapped_group_count": ident.unmapped_group_count,
            "non_guid_group_claims": p.non_guid_group_claims,
            "group_source": ident.group_source,
            "config_version": ident.snapshot.version,
        }
        if explain:
            result["policy"] = ident.policy.explain()
        return result

    async def list_skills() -> list[dict[str, str]]:
        """List the SDLC skills available to you (name + description). Load one with load_skill."""
        ident = await request_identity()
        skills = ident.snapshot.skills
        visible = sorted(ident.policy.skills)
        audit_skills_list(ident, visible, len(skills) - len(visible))
        return [{"name": name, "description": skills[name].description} for name in visible]

    async def load_skill(name: str) -> dict[str, str]:
        """Return the full instructions of a skill returned by list_skills."""
        ident = await request_identity()
        decision = skill_decision(ident.snapshot, ident.policy, name)
        audit_skill_access(ident, name, decision)  # the audit records the real reason
        # Hidden and non-existent skills get the same answer: existence is not disclosed.
        if not decision.allowed:
            raise ToolError(f"unknown skill '{name}'")
        skill = ident.snapshot.skills[name]
        return {
            "name": skill.name,
            "description": skill.description,
            "instructions": skill.instructions,
        }

    async def get_agent_context() -> dict:
        """Your team instructions and context, to apply for the whole session."""
        policy = (await request_identity()).policy
        return {
            "instructions": [
                {"team": item.team, "source": item.source, "text": item.text}
                for item in policy.agent_instructions
            ],
            "context": {team: dict(values) for team, values in policy.context.items()},
            "config_version": policy.config_version,
        }

    core = [ping, whoami, list_skills, load_skill, get_agent_context]
    knowledge_tools = make_knowledge_tools(knowledge) if knowledge else []
    for fn in [*core, *SDLC_TOOLS, *make_admin_tools(store, cache), *knowledge_tools]:
        register(fn)

    # Catalog vs code: fail startup on bad constraint args; re-check (log) on every reload.
    problems = catalog_problems(store.current(), registered)
    if problems:
        raise ValueError("config does not match the registered tools: " + "; ".join(problems))
    uncatalogued = sorted(set(registered) - set(store.current().tools))
    if uncatalogued:
        log.warning("tools not in tools.yaml are never exposed: %s", uncatalogued)

    def recheck(snapshot: Snapshot) -> None:
        for problem in catalog_problems(snapshot, registered):
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


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(message)s")
    store = ConfigStore.from_env()  # raises ConfigError on invalid config: fail closed
    if os.environ.get("SDLC_CONFIG_WATCH", "true").lower() == "true":
        store.start_watching()
    snapshot = store.current()
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8080"))
    knowledge = build_knowledge(snapshot)
    server = build_server(
        store,
        build_auth(snapshot, os.environ.get("MCP_PUBLIC_URL", f"http://127.0.0.1:{port}"), store),
        build_group_resolver(snapshot),
        knowledge,
    )
    uvicorn.run(build_http_app(server, store), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
