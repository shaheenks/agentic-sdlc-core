"""Bootstrap MCP server.

Stage 1: ping, list_skills, load_skill over streamable HTTP.
Stage 2: every MCP request needs a valid Entra ID user token (401 otherwise); whoami;
         config via ConfigStore (fail closed); JSON audit log for every tool call.
Stage 3 adds RBAC: tools/list filtering and per-call authorization from config/.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AuthProvider, RemoteAuthProvider
from sdlc_auth import GraphGroupResolver, GroupResolver
from sdlc_auth.entra import EntraTokenVerifier
from sdlc_config import ConfigStore, Snapshot
from starlette.requests import Request
from starlette.responses import JSONResponse

from sdlc_mcp_bootstrap.audit import AuditMiddleware
from sdlc_mcp_bootstrap.identity import current_identity

log = logging.getLogger("sdlc.mcp")

DEFAULT_SKILLS_DIR = Path(__file__).resolve().parents[4] / "skills" / "bootstrap"


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    instructions: str


def parse_skill(path: Path) -> Skill:
    """Parse a SKILL.md file: YAML frontmatter (name, description) + markdown body."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path}: missing YAML frontmatter")
    _, frontmatter, body = text.split("---", 2)
    meta = yaml.safe_load(frontmatter) or {}
    for key in ("name", "description"):
        if not meta.get(key):
            raise ValueError(f"{path}: frontmatter is missing '{key}'")
    return Skill(name=meta["name"], description=meta["description"], instructions=body.strip())


def discover_skills(skills_dir: Path) -> dict[str, Skill]:
    """Load every <skills_dir>/<skill>/SKILL.md, keyed by skill name."""
    skills: dict[str, Skill] = {}
    for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
        skill = parse_skill(skill_file)
        if skill.name in skills:
            raise ValueError(f"duplicate skill name '{skill.name}' in {skills_dir}")
        skills[skill.name] = skill
    return skills


def build_server(
    skills_dir: Path,
    store: ConfigStore,
    auth: AuthProvider,
    group_resolver: GroupResolver | None = None,
) -> FastMCP:
    # Skills are loaded once at startup so a malformed SKILL.md fails fast.
    skills = discover_skills(skills_dir)
    mcp = FastMCP(
        name="sdlc-mcp-bootstrap",
        instructions="Central SDLC tool server. Use list_skills, then load_skill before a task.",
        auth=auth,
        middleware=[AuditMiddleware(store)],
    )

    @mcp.tool
    def ping() -> str:
        """Liveness check. Returns 'pong'."""
        return "pong"

    @mcp.tool
    async def whoami() -> dict:
        """Who the server thinks you are: Entra identity and mapped group aliases."""
        ident = await current_identity(store.current(), group_resolver)
        p = ident.principal
        return {
            "oid": p.oid,
            "upn": p.upn,
            "name": p.name,
            "tenant_id": p.tid,
            "groups": list(ident.group_aliases),
            "unmapped_group_count": ident.unmapped_group_count,
            "group_source": ident.group_source,
            "config_version": ident.config_version,
        }

    @mcp.tool
    def list_skills() -> list[dict[str, str]]:
        """List available SDLC skills (name + description). Load one with load_skill."""
        return [{"name": s.name, "description": s.description} for s in skills.values()]

    @mcp.tool
    def load_skill(name: str) -> dict[str, str]:
        """Return the full instructions of a skill returned by list_skills."""
        skill = skills.get(name)
        if skill is None:
            raise ToolError(f"unknown skill '{name}'")
        return {
            "name": skill.name,
            "description": skill.description,
            "instructions": skill.instructions,
        }

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "skills": len(skills),
                "config_version": store.current().version,
                "config_reload_error": store.last_error is not None,
            }
        )

    return mcp


def build_auth(snapshot: Snapshot, public_url: str) -> RemoteAuthProvider:
    """Entra token verification + OAuth protected-resource metadata (RFC 9728).

    The 401 WWW-Authenticate header points MCP clients (e.g. Antigravity) at
    /.well-known/oauth-protected-resource, which names Entra as the authorization server.
    Identity settings are read once at startup; changing them needs a restart.
    """
    platform = snapshot.platform
    verifier = EntraTokenVerifier(
        tenant_id=platform.tenant_id,
        audience=list(platform.audience),
        required_scopes=list(platform.required_scopes),
        issuer=platform.issuer,
        jwks_uri=platform.jwks_uri,
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
    )


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(message)s")
    store = ConfigStore.from_env()  # raises ConfigError on invalid config: fail closed
    if os.environ.get("SDLC_CONFIG_WATCH", "true").lower() == "true":
        store.start_watching()
    snapshot = store.current()
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8080"))
    server = build_server(
        Path(os.environ.get("SDLC_SKILLS_DIR", DEFAULT_SKILLS_DIR)),
        store,
        build_auth(snapshot, os.environ.get("MCP_PUBLIC_URL", f"http://127.0.0.1:{port}")),
        build_group_resolver(snapshot),
    )
    server.run(transport="http", host=host, port=port)


if __name__ == "__main__":
    main()
